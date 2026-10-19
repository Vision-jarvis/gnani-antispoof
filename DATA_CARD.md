# Data card

## Sets actually used for the numbers in this repo

| Set | Built by | Size | Content | Licence |
|---|---|---|---|---|
| ASVspoof 2019 LA train subset | `python -m factory.asvspoof --split train --n-bona 2580 --n-spoof-per-attack 430` | 5,160 utts (2,580 bona fide = all; 430 of each of A01 to A06) | each utterance as `nb_pcm` plus one seen codec drawn by hash | ODC-By 1.0 |
| ASVspoof 2019 LA dev subset | `--split dev --n-bona 1000 --n-spoof-per-attack 170` | 2,020 utts | same as train (used only for thresholds, calibration, model selection) | ODC-By 1.0 |
| ASVspoof 2019 LA eval subset | `--split eval --n-bona 1000 --n-spoof-per-attack 120` | 2,560 utts (A07 to A19) | every utterance under all 14 channel conditions plus clean 16 kHz | ODC-By 1.0 |
| Indic pilot | `python -m factory.indic_pilot --per-class-per-lang 300` | 1,200 utts | FLEURS test bona fide (hi, kn) vs IndicSynth FreeVC (G4, hi, kn), under 6 channel conditions | CC-BY-4.0 / CC-BY-NC-4.0 |

Selection is deterministic: utterances are ordered by SHA-1 of their ID and the first N per class or
attack are taken (`factory/asvspoof.py: select`). ASVspoof train, dev and eval have disjoint speakers by
construction.

## Processing applied identically to every clip
1. Raw statistics recorded before any processing: leading and trailing silence, integrated loudness,
   duration (`manifest.csv`, used by the shortcut audit).
2. `factory.normalise.normalise`: energy VAD trim with 50 ms of original context kept, then -23 LUFS.
3. `factory.channel_sim`: 8 kHz conditions (seed = hash of utterance ID):

| Condition | Chain | Role |
|---|---|---|
| nb_pcm | resample to 8 kHz | seen (clean narrowband reference) |
| g711u, g711a | PSTN band-pass 300 to 3400 Hz + G.711 | seen |
| amrnb_12k2, amrnb_7k95 | AMR-NB | seen |
| amrwb_12k65 | AMR-WB at 16 kHz, then down to 8 kHz | seen |
| opus_8k, opus_16k | Opus narrowband, CBR, VoIP mode | seen |
| opus_6k_plc3 | Opus 6 kbps + 3% packet loss | seen |
| g711u_plc5 | G.711 mu-law + 5% packet loss | seen |
| amrnb_4k75 | AMR-NB 4.75 kbps | **held out** |
| gsm_fr | GSM full rate | **held out** |
| chain_amrnb_g711u | AMR-NB 7.95k then band-pass + G.711 mu-law (mobile to PSTN) | **held out** |
| chain_gsm_g711a_plc2 | GSM-FR then G.711 A-law with 2% loss | **held out** |

## Known biases and gaps
- ASVspoof 2019 LA is English read speech from VCTK speakers, with 2019-era TTS/VC systems. It is not
  Indic and not telephony. It is a proxy for the channel effect only.
- Channels are simulated (ffmpeg reference codecs, synthetic packet loss); no real PSTN or VoIP path.
- The Indic pilot's bona fide and spoof come from different corpora (FLEURS vs IndicSynth), a corpus
  confound; its shortcut audit is reported alongside its EERs.
- IndicSynth and MLAAD are CC-BY-NC: fine for research and the challenge entry, not for a commercial
  Armour365 model.
- Real Gnani clone data (G1 to G3) is not generated yet; only 5 probe calls were made
  (`docs/gnani_api_notes.md`). Cloned audio of corpus speakers must never be published (rule 7).
