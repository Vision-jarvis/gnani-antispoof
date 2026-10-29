# Data and models used (licences, how to get them, what is redistributed)

The code is MIT (`LICENSE`). Nothing under `data/`, `third_party/` or `artifacts/gnani_cache/` is committed.
`release/` is the only data that is committed: ASVspoof 2019 LA manifests and a 120-clip G.711 eval pack,
redistributed under ODC-By 1.0 with the attribution below, plus models and scores this repo produced.

| Item | Licence | How it is obtained | Used for | Redistributed here? |
|---|---|---|---|---|
| ASVspoof 2019 LA (train/dev/eval) | ODC-By 1.0 (Wang et al. 2020, University of Edinburgh). The HF mirror `Bisher/ASVspoof_2019_LA` states no licence; its row counts equal the official protocol | `bash scripts/download_data.sh` (mirror); manual DataShare steps in `data/README.md` | every ASVspoof table | manifests + 120 G.711 clips in `release/` (attribution: "ASVspoof 2019 LA, ODC-By 1.0") |
| ASVspoof 2021 LA eval + keys | ODC-By 1.0 | Zenodo 4837263, asvspoof.org | PENDING sanity check | no |
| In-the-Wild | CC-BY-SA-4.0 | HF `mueller91/In-The-Wild` | PENDING sanity check | no |
| FLEURS (hi, kn) | CC-BY-4.0 | HF `google/fleurs` | Indic pilot bona fide; sentence source for Gnani generation | no |
| IndicSynth (hi, kn, FreeVC shards) | CC-BY-NC-4.0, research only | HF `vdivyasharma/IndicSynth` | Indic pilot spoofs (G4, eval only) | no |
| Kathbath | HF metadata CC-BY-4.0 (text says CC0); gated (accept terms) | HF `ai4bharat/Kathbath`, manual | PENDING bona fide Indic pool. Cloning Kathbath speakers is **DEFERRED** pending Gnani's written consent clearance | no |
| MLAAD | CC-BY-NC-4.0, gated | HF, manual | not used | no |
| clovaai/aasist code + AASIST / AASIST-L weights | MIT (NAVER) | `git clone` into `third_party/aasist` (`run.ps1 setup`) | pretrained SOTA scoring | no |
| TakHemlata/SSL_Anti-spoofing code + `LA_model.pth` | MIT (code); checkpoint published by the authors on Google Drive | `git clone`; `python -m gdown 11vFBNKzYUtWqdK358_JEygawFzmmaZjO -O third_party/ssl_ckpt/LA_model.pth` | pretrained SOTA scoring, teacher back-end | no |
| facebook/wav2vec2-xls-r-300m | Apache-2.0 | downloaded by `transformers` on the GPU box | teacher front-end | no |
| speechbrain/spkrec-ecapa-voxceleb | Apache-2.0 | optional, not installed | PENDING ASV | no |
| Gnani Timbre v2.5, Prisma v2.5 (and an opt-in Prisma v3.0 phrase check), voice-clone API | proprietary, challenge credits | `.env` key (git-ignored) | IVR flow, G1/G3 Timbre stock voices, G2/G3 of the builder's own consented voice | no Gnani audio is ever committed (`artifacts/gnani_cache/` is git-ignored); no cloned audio is ever published; scores, transcripts of the builder's own answers and decision codes only. The only Gnani audio public material may contain is the Timbre stock-voice IVR prompt in the demo video |
| Builder's own voice recordings (`data/own_voice/`) | the author's, consented (`consent=self`) | recorded by the author (`docs/RECORDING.md`; fixed phrases, no personal data) | G2/G3 red team, Prisma phrase check, live demo | no: `data/` and every audio file type are git-ignored; the Modal copy used for teacher scoring is deleted after the run |

Models in `release/models/` (`lcnn8_aug.pt`, `cm_student.onnx`, `gmm8_aug.npz`) were trained here on ASVspoof
2019 LA only (ODC-By), so they carry no non-commercial restriction; anything later trained on IndicSynth or
MLAAD would be research-only.
