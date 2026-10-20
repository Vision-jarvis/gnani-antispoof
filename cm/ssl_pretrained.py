"""Pretrained SSL + AASIST (Tak et al., Odyssey 2022, ``LA_model.pth``) without fairseq.

The published checkpoint stores the fine-tuned XLS-R 300M front-end with fairseq parameter names. This module
renames them to the Hugging Face ``Wav2Vec2Model`` layout used by ``cm.teacher.model.HFSSLFrontEnd`` (the same
renaming as transformers' fairseq conversion script), so the published model loads with ``strict=True`` into
the teacher architecture and needs no fairseq install. The pre-training-only heads (quantizer, project_q,
final_proj, mask_emb) are dropped; ``features_only`` inference never uses them.

Checkpoint (public, from the SSL_Anti-spoofing README): Google Drive file 11vFBNKzYUtWqdK358_JEygawFzmmaZjO
  python -m gdown 11vFBNKzYUtWqdK358_JEygawFzmmaZjO -O third_party/ssl_ckpt/LA_model.pth
Scoring follows the authors' eval code: first 64,600 samples at 16 kHz, repeat-padded, score = output[:, 1].
"""

from __future__ import annotations

import re
from pathlib import Path

import torch
from torch import nn

ROOT = Path(__file__).resolve().parents[1]
CKPT = ROOT / "third_party" / "ssl_ckpt" / "LA_model.pth"
DROP = ("quantizer.", "project_q.", "final_proj.")
LAYER_MAP = {
    "self_attn.k_proj": "attention.k_proj",
    "self_attn.v_proj": "attention.v_proj",
    "self_attn.q_proj": "attention.q_proj",
    "self_attn.out_proj": "attention.out_proj",
    "self_attn_layer_norm": "layer_norm",
    "fc1": "feed_forward.intermediate_dense",
    "fc2": "feed_forward.output_dense",
    "final_layer_norm": "final_layer_norm",
}


def xlsr_300m_config():  # noqa: ANN201 - transformers type
    """facebook/wav2vec2-xls-r-300m architecture, built offline (weights come from the checkpoint)."""
    from transformers import Wav2Vec2Config

    return Wav2Vec2Config(hidden_size=1024, num_hidden_layers=24, num_attention_heads=16, intermediate_size=4096,
                          feat_extract_norm="layer", do_stable_layer_norm=True, conv_bias=True,
                          num_conv_pos_embeddings=128, num_conv_pos_embedding_groups=16, feat_proj_dropout=0.0,
                          hidden_dropout=0.0, attention_dropout=0.0, activation_dropout=0.0, layerdrop=0.0,
                          mask_time_prob=0.0)


def rename_fairseq(key: str, pos_conv_names: dict[str, str]) -> str | None:
    """fairseq wav2vec 2.0 parameter name -> Hugging Face Wav2Vec2Model name (None = drop)."""
    if key.startswith(DROP):
        return None
    if key == "mask_emb":
        return None  # training-time masking vector; the config sets mask_time_prob = 0, so HF has no slot for it
    if key.startswith("post_extract_proj."):
        return key.replace("post_extract_proj.", "feature_projection.projection.")
    if key.startswith("layer_norm."):
        return key.replace("layer_norm.", "feature_projection.layer_norm.")
    if key.startswith("encoder.layer_norm."):
        return key
    m = re.match(r"feature_extractor\.conv_layers\.(\d+)\.(0|2\.1)\.(weight|bias)$", key)
    if m:
        part = "conv" if m.group(2) == "0" else "layer_norm"
        return f"feature_extractor.conv_layers.{m.group(1)}.{part}.{m.group(3)}"
    m = re.match(r"encoder\.pos_conv\.0\.(weight_g|weight_v|bias)$", key)
    if m:
        return pos_conv_names[m.group(1)]
    m = re.match(r"encoder\.layers\.(\d+)\.(.+)\.(weight|bias)$", key)
    if m and m.group(2) in LAYER_MAP:
        return f"encoder.layers.{m.group(1)}.{LAYER_MAP[m.group(2)]}.{m.group(3)}"
    raise KeyError(f"unmapped fairseq key {key}")


def convert_state_dict(sd: dict[str, torch.Tensor], hf_keys: set[str]) -> dict[str, torch.Tensor]:
    """Rename the ``ssl_model.model.*`` part of an SSL+AASIST state dict; back-end keys pass through."""
    if "encoder.pos_conv_embed.conv.weight_g" in hf_keys:  # older torch weight_norm
        pos = {"weight_g": "encoder.pos_conv_embed.conv.weight_g", "weight_v": "encoder.pos_conv_embed.conv.weight_v"}
    else:  # torch.nn.utils.parametrizations.weight_norm
        pos = {"weight_g": "encoder.pos_conv_embed.conv.parametrizations.weight.original0",
               "weight_v": "encoder.pos_conv_embed.conv.parametrizations.weight.original1"}
    pos["bias"] = "encoder.pos_conv_embed.conv.bias"
    out = {}
    for k, v in sd.items():
        if k.startswith("ssl_model.model."):
            new = rename_fairseq(k[len("ssl_model.model."):], pos)
            if new is not None:
                out[f"ssl_model.model.{new}"] = v
        else:
            out[k] = v
    return out


def load_ssl_aasist(ckpt: Path = CKPT, device: str = "cpu") -> nn.Module:
    """The published LA model in the teacher architecture, eval mode."""
    from cm.teacher.model import HFSSLFrontEnd, build_teacher

    model = build_teacher(HFSSLFrontEnd(xlsr_300m_config()))
    sd = torch.load(ckpt, map_location="cpu", weights_only=False)
    hf_keys = {k[len("ssl_model.model."):] for k in model.state_dict() if k.startswith("ssl_model.model.")}
    model.load_state_dict(convert_state_dict(sd, hf_keys), strict=True)
    return model.to(device).eval()
