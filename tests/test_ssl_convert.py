"""fairseq -> Hugging Face renaming for the published SSL+AASIST checkpoint (no download needed)."""

from __future__ import annotations

import torch

from cm.ssl_pretrained import convert_state_dict, rename_fairseq

POS = {"weight_g": "encoder.pos_conv_embed.conv.weight_g", "weight_v": "encoder.pos_conv_embed.conv.weight_v",
       "bias": "encoder.pos_conv_embed.conv.bias"}


def test_rename_core_keys() -> None:
    assert rename_fairseq("feature_extractor.conv_layers.3.0.weight", POS) == "feature_extractor.conv_layers.3.conv.weight"
    assert rename_fairseq("feature_extractor.conv_layers.3.2.1.bias", POS) == "feature_extractor.conv_layers.3.layer_norm.bias"
    assert rename_fairseq("encoder.layers.7.self_attn.q_proj.weight", POS) == "encoder.layers.7.attention.q_proj.weight"
    assert rename_fairseq("encoder.layers.7.fc2.bias", POS) == "encoder.layers.7.feed_forward.output_dense.bias"
    assert rename_fairseq("layer_norm.weight", POS) == "feature_projection.layer_norm.weight"
    assert rename_fairseq("encoder.layer_norm.weight", POS) == "encoder.layer_norm.weight"
    assert rename_fairseq("quantizer.vars", POS) is None and rename_fairseq("mask_emb", POS) is None


def test_backend_keys_pass_through() -> None:
    sd = {"ssl_model.model.encoder.pos_conv.0.weight_g": torch.zeros(1), "LL.weight": torch.ones(1)}
    out = convert_state_dict(sd, {"encoder.pos_conv_embed.conv.weight_g"})
    assert set(out) == {"ssl_model.model.encoder.pos_conv_embed.conv.weight_g", "LL.weight"}
