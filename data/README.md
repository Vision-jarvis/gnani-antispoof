# Data: what is here, where it came from, and what needs a manual step

Everything under `data/` except this file is git-ignored. Licences were checked on the dataset pages
on 18 Oct 2026.

## Downloaded automatically (`bash scripts/download_data.sh`, resumable curl)

| Dataset | Source used | Licence | Status | Used for |
|---|---|---|---|---|
| ASVspoof 2019 LA train / dev / eval (25,380 / 24,844 / 71,237 utts) | HF mirror `Bisher/ASVspoof_2019_LA` (parquet with speaker and system IDs; row counts equal the official protocol) | ODC-By 1.0 (original; the mirror states none) | done, 7.5 GB | CPU baselines, all ASVspoof tables |
| ASVspoof 2021 LA keys (`LA-keys-full.tar.gz`) | asvspoof.org | ODC-By 1.0 | done | 2021 LA sanity check (PENDING scoring) |
| ASVspoof 2021 LA eval audio (7.76 GB) | Zenodo record 4837263 | ODC-By 1.0 | partial: the download was interrupted by a DNS outage; resume with the command below | PENDING sanity check |
| IndicSynth, first shard of Hindi and Kannada (FreeVC, 1,925 + 1,264 clips) | HF `vdivyasharma/IndicSynth` | CC-BY-NC-4.0 (non-commercial) | done | G4 attacks in the Indic pilot |
| FLEURS Hindi + Kannada dev/test | HF `google/fleurs` | CC-BY-4.0 | done | Indic bona fide stand-in, sentence source for Gnani generation |
| In-the-Wild (8.2 GB zip) | HF `mueller91/In-The-Wild` | CC-BY-SA-4.0 | not finished (same DNS outage) | PENDING out-of-domain sanity check |

Resume the interrupted downloads:

```bash
bash scripts/download_data.sh   # finished files are skipped by curl -C -, partial ones resume
```

## Needs a manual step (do not script around these)

1. **Edinburgh DataShare (official ASVspoof 2019 host, handle 10283/3336).** The server closed every
   connection from this machine (curl, PowerShell and WebFetch all got an empty reply). The HF mirror
   above has identical row counts. If you want the official zip for provenance: open
   https://datashare.ed.ac.uk/handle/10283/3336 in a browser and download `LA.zip` (7.12 GB).
2. **Kathbath (bona fide Indic, required for the real IndicClone-Tel).** HF `ai4bharat/Kathbath` is gated
   ("auto" approval). Log in to huggingface.co, open the dataset page and accept the terms, then
   `huggingface-cli login` and download the Hindi and Kannada splits (about 3 h each). Note: the HF page
   tags the licence as CC-BY-4.0, while the problem statement says CC0; cite the HF page.
3. **MLAAD (multilingual spoof training data).** HF `mueller91/MLAAD` is gated in the same way and is
   CC-BY-NC-4.0 (research only; a production Armour365 model would need Gnani's own licensed data).
4. **Gnani clone set (G1, G2, G3).** Not a download: generated with the student's challenge key by
   `factory/gnani_clone.py`, which needs explicit approval (`--execute --max-calls N`). See
   `docs/gnani_api_notes.md`. Clones of Kathbath speakers are for scoring only and must not be published.

## Built locally

- `data/proc/asv19/{train,dev,eval}/`: VAD-trimmed, loudness-normalised subsets, one packed `.npz`
  per channel condition, plus `manifest.csv` (speaker, attack, raw silence/loudness/duration stats).
  Built by `python -m factory.asvspoof` (see `scripts/run_pipeline.sh` for the exact sizes).
- `data/proc/indic_pilot/eval/`: FLEURS + IndicSynth pilot, built by `python -m factory.indic_pilot`.
