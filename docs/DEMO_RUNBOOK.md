# Day 30 runbook: Oct 30 rehearsal, the Nov 1 run sheet, the Nov 2 video

All times IST. Commands run in PowerShell from the repo folder (`builds\gnani-antispoof`) with the venv python
(`.\.venv\Scripts\python`). Every live step prints its plan first and needs `--execute` plus a hard `--max-calls`
cap, or is a single explicit call. After each step, `scripts\day30_outputs.py` prints the exact values for the
post placeholders in `posts/day30-28_gnani.md` (it reads the run outputs; it never edits the post).
Rules that hold all day: nobody prints, opens or pastes `.env`; no cloned audio is ever posted or committed;
outcomes are reported as they come out, including failures; no step is rerun to get a nicer number.

## Gnani calls and credits

| Step | Calls | Cap |
|---|---|---|
| 08:45 key check (optional, `.\run.ps1 live-test`) | 2 | fixed |
| 10:00 clone run: 1 embedding + 15 VC TTS (10 as 16 kHz WAV, 5 as 8 kHz mu-law), 644 characters | 16 | `--max-calls 16` |
| 16:00 Prisma v2.5 vs v3.0: 10 answers x 2 models (REST) | 20 | `--max-calls 20` |
| 18:00 live IVR: 1 Timbre prompt + 1 VC TTS + 2 Prisma realtime sessions | 4 | one call per command |
| Total | 40 (42 with the key check) | |

The API returns no usage data and the price per call or character is not published (`docs/gnani_api_notes.md`),
so credits are measured, not estimated: read the balance on app.gnani.ai before 10:00 and after 18:30 and pass
both numbers to `day30_outputs.py` (`--credits-before`, `--credits-after`). Every registrant has 5,000 programme
credits; the only spend so far is the 5 probe calls of Oct 18.

## Oct 30 to 31: rehearsal (no API calls, no Modal)

Student, Oct 30:
1. Rotate the Gnani API key on app.gnani.ai (the old one has been in agent sessions). Open `.env` in Notepad
   yourself and set the line `GNANI_API_KEY=<new key>`. Never paste the key into a chat or a terminal command.
2. Check that the key is found without printing it:
   `.\.venv\Scripts\python -c "from gnani_api import load_api_key; print('key found' if load_api_key() else 'NO KEY')"`
3. Note the credit balance on app.gnani.ai.
4. Make the 2-minute test recording (`docs/RECORDING.md`, "Oct 30") and run
   `.\.venv\Scripts\python scripts\prep_own_voice.py --root data/own_voice/test --subset test`; send the printout.

Agent, Oct 30 to 31: rehearse every Nov 1 command on the test takes in mock mode, writing outputs outside
`artifacts/` (stand-in spoofs: ASVspoof spoof clips in a scratch folder outside the repo):

```powershell
$T = "data/own_voice/test"; $X = "<scratch folder outside the repo>"
.\.venv\Scripts\python -m factory.gnani_clone --speakers factory/manifests/demo_builder_voice.csv          # dry run only
.\.venv\Scripts\python scripts\prep_own_voice.py trialsets --root $T --spoof-src $X\spoof_src
.\.venv\Scripts\python -m ivr_demo.trials --bona-dir $T/trials/g711u/bona --spoof-dir $T/trials/g711u/spoof --tag ownvoice_g711u --out-dir $X
.\.venv\Scripts\python -m ivr_demo.trials --bona-dir $T/trials/amrnb_4k75/bona --spoof-dir $T/trials/amrnb_4k75/spoof --tag ownvoice_amrnb_4k75 --out-dir $X
.\.venv\Scripts\python -m cm.teacher.score_folder --root $T/trials --device cpu --out $X/ownvoice_teacher_scores.csv
.\.venv\Scripts\python -m ivr_demo.phrase_check --audio-dir $T/16k --mock --out $X/prisma_phrase_check.json
.\.venv\Scripts\python -m ivr_demo.demo --live --mock --new-challenge --language hi-IN
.\.venv\Scripts\python -m ivr_demo.demo --live --mock --caller $T/16k/answer_01.wav --clone --operating-point min_dcf --out $X/ivr_live.json
.\.venv\Scripts\python scripts\day30_outputs.py --rehearsal --trials-dir $X --teacher $X/ownvoice_teacher_scores.csv --phrase $X/prisma_phrase_check.json --live $X/ivr_live.json --png $X/gnani_ownvoice_rehearsal.png
```

The same sequence already ran end to end on Oct 29 on ASVspoof stand-ins (17 takes: 15 bona fide clips of one
speaker re-encoded as 48 kHz stereo AAC, 15 spoof clips as clones): every step exited 0, the clone dry run
showed 16 calls and 644 characters, the teacher scored 60 clips on CPU in 34 s (44 s with model loading), and
`day30_outputs.py` printed every placeholder and drew the watermarked chart. Mock outputs are labelled MOCK
and `day30_outputs.py` refuses to write a mock chart into `posts/img/`.

## Nov 1 run sheet

| Time | Who | Step | Command | Runtime | Output files |
|---|---|---|---|---|---|
| 08:30 | agent | preflight | `git status --short` (clean), `.\.venv\Scripts\python -m pytest`, `modal volume ls gnani-cm-data /artifacts_teacher_v2/models` (the checkpoint is there) | 3 min | none |
| 08:45 | student | balance + key | read the credit balance (before); optional `.\run.ps1 live-test` (2 calls) | 2 min | none |
| 09:00 | student | record | the 17 takes of `docs/RECORDING.md` into `data\own_voice\raw\` | 15 min | `data/own_voice/raw/*.m4a` |
| 09:15 | student or agent | convert | `.\.venv\Scripts\python scripts\prep_own_voice.py` | 5 s | `data/own_voice/{16k,8k}/*.wav`, `data/own_voice/builder_15s.wav`, `data/own_voice/prep_report.json` |
| 09:30 | student | problem post | posts/day30-28_gnani.md | | |
| 10:00 | agent | clone plan | `.\.venv\Scripts\python -m factory.gnani_clone --speakers factory/manifests/demo_builder_voice.csv` | 2 s | expect `"pending_calls": 16`, `"pending_chars": 644`, no WARNING line |
| 10:05 | agent | clone run | `.\.venv\Scripts\python -m factory.gnani_clone --speakers factory/manifests/demo_builder_voice.csv --execute --max-calls 16` | 1 to 2 min | `artifacts/gnani_cache/G2/*.json` (embedding), `G2/*.wav` (10), `G3/*.mulaw` (5), `artifacts/gnani_cache/jobs_demo_builder_voice.csv`, `artifacts/gnani_usage.jsonl` |
| 10:10 | student | listen privately | play 2 or 3 of `artifacts\gnani_cache\G2\*.wav` for the [3 WORDS] verdict; read the balance again | 5 min | none |
| 10:15 | agent | trial sets | `.\.venv\Scripts\python scripts\prep_own_voice.py trialsets` | 10 s | `data/own_voice/trials/{g711u,amrnb_4k75}/{bona,spoof}/*.wav` (15 + 15 each), `data/own_voice/trials/index.csv` |
| 10:20 | agent | update 2 numbers | `.\.venv\Scripts\python scripts\day30_outputs.py --credits-before <B> --credits-after <A>` | 5 s | prints [N] and [CREDITS] |
| 12:30 | agent | teacher (CPU, default) | `.\.venv\Scripts\python -m cm.teacher.score_folder --root data/own_voice/trials --device cpu --out artifacts/ownvoice_teacher_scores.csv` | about 45 s | `artifacts/ownvoice_teacher_scores.csv` (no upload of your voice, no cost; the "$9.58 on Modal" line stays true) |
| 13:00 | student | update 2 | post | | |
| 14:00 | agent | trials, small CPU model | `.\.venv\Scripts\python -m ivr_demo.trials --bona-dir data/own_voice/trials/g711u/bona --spoof-dir data/own_voice/trials/g711u/spoof --tag ownvoice_g711u` and the same with `amrnb_4k75` | 10 s each | `artifacts/ivr_trials_ownvoice_{g711u,amrnb_4k75}.{json,md}` and `_scores.csv` |
| 14:10 | agent | update 3 numbers + chart | `.\.venv\Scripts\python scripts\day30_outputs.py --credits-before <B> --credits-after <A>` | 5 s | prints both [RESULT] lines, writes `posts/img/gnani_ownvoice.png` |
| 15:30 | student | update 3 | post with the chart | | |
| 16:00 | agent | Prisma plan | `.\.venv\Scripts\python -m ivr_demo.phrase_check` | 5 s | expect "10 answers ... 20 STT calls needed" |
| 16:05 | agent | Prisma v2.5 vs v3.0 | `.\.venv\Scripts\python -m ivr_demo.phrase_check --execute --max-calls 20` | about 1 min | `artifacts/prisma_phrase_check.json`, transcripts cached in `artifacts/gnani_cache/stt/` |
| 16:10 | agent | update 4 numbers | `day30_outputs.py` again; post only if it says `v3.0 opt-in confirmed: True` | 5 s | prints [N] and [X] -> [Y] |
| 17:00 | student | update 4 | quote Gnani's Prisma v3.0 post; one reply under Ruchi's post | | |
| 18:00 | both | live IVR, see below | | 10 min | `artifacts/ivr_live.json` |
| 18:30 | student | update 5 | post with a screenshot of the decision lines | | |
| 20:30 | agent | wrap | `day30_outputs.py` (all sections), then commit the result files only (below) | 10 min | |

Teacher on Modal instead (only if the CPU run fails): `modal volume put gnani-cm-data data/own_voice/trials /ownvoice/trials --force`, `modal run --detach cm/teacher/modal_train.py::ownvoice_main`, then `ownvoice_fetch` and `modal volume rm -r gnani-cm-data /ownvoice` (about $0.10 to $0.20; update the Modal cost line in the posts). The CPU path writes
the same `artifacts/ownvoice_teacher_scores.csv`; it took 44 s for 60 clips on this laptop in the rehearsal. In
Git Bash, set `export MSYS_NO_PATHCONV=1` before any `modal volume` command. The Modal job reuses the teacher image
and the best checkpoint already on the volume; its 20-minute timeout caps the cost at about $0.47.

If the clone run stops on a Hinglish text (the VC model may reject Latin script), rerun the same command with
`--alt-text --max-calls 10`: the five Hindi answers are cached, and the Hinglish clones are made from the
Devanagari spellings in `alt_text` instead. Any other error: the run stops, keeps what it made, and the same
command resumes it.

### 18:00 live IVR, step by step

1. Student: start the screen recording (Win+Alt+R) on the terminal window.
2. Agent or student: `.\.venv\Scripts\python -m ivr_demo.demo --live --new-challenge --language hi-IN`
   (1 Timbre call, about 3 s). It prints the fresh random phrase and saves `artifacts/gnani_cache/ivr_challenge.json`
   and `artifacts/gnani_cache/ivr_prompt.wav`.
3. Student: `start artifacts\gnani_cache\ivr_prompt.wav` to hear the IVR, then record the answer once in Sound
   Recorder and save it as `data\own_voice\raw\live_answer.m4a`.
4. `.\.venv\Scripts\python scripts\prep_own_voice.py --only live_answer` (2 s).
5. `.\.venv\Scripts\python -m ivr_demo.demo --live --caller data/own_voice/16k/live_answer.wav --clone --operating-point min_dcf`
   (1 VC TTS call and 2 Prisma realtime sessions, about 20 to 30 s, because realtime STT streams at speaking
   speed). It reads every input before the first call, then prints for "genuine" and "clone": StatusCode,
   DecisionCode, reason, CM LLR, local decision latency, Prisma end-of-speech-to-transcript delay, and the codes
   at far1 and eer from the same transcripts (no extra calls). The identity gate is bypassed and says so (ECAPA
   is PENDING); add `--asv lfcc --enrol data/own_voice/16k/enrol.wav` only to show the stand-in, which is not a
   speaker verifier.
6. `.\.venv\Scripts\python scripts\day30_outputs.py ...` for the [DECISION CODE] and [LATENCY] lines. Stop the
   recording. Do not rerun the call to get a different outcome; if a rerun is unavoidable (a crash), say so in the
   post.

The posts say "a speaker model checks it's me" (update 5) and "ECAPA stands in for speaker matching" (Day 29,
7/): neither is true of this run, because the identity gate is bypassed. Fix that wording before posting.

### 20:30 commit the results (agent)

Result files are scores and decisions only: `artifacts/ivr_trials_ownvoice_*`, `artifacts/ownvoice_teacher_scores.csv`,
`artifacts/scores/teacher_ownvoice_cost.json`, `artifacts/prisma_phrase_check.json`, `artifacts/ivr_live.json`. Add
the own-voice rows to README, REPORT section 4 and STATUS with these numbers and n, then check that
`git status --short` lists no audio and nothing under `data/` or `artifacts/gnani_cache/` before committing.

## Nov 2 morning: the 60 s video

Shot list (each number on screen comes from `artifacts/results.md` or the Nov 1 output files):
1. (0 to 6 s) Text: "Banks let callers verify by voice. My clone was made from 15 s of my voice."
2. (6 to 15 s) The 10:00 clone run in the terminal (16 calls, [N] clips) and you recording the reference. Do not
   play the clone: no cloned audio is published (honesty rule 7). Caption: "clone audio not shown, on purpose".
3. (15 to 25 s) `posts/img/gnani_ownvoice.png`: your real answers vs the clone through G.711 and AMR-NB, small CPU
   model vs the fine-tuned teacher, dev thresholds marked. Caption the two [RESULT] lines.
4. (25 to 40 s) The 18:00 screen recording: the challenge phrase, the Timbre prompt (a stock voice), your answer,
   the clone's answer, the printed DecisionCodes and latency, with the operating point line ("min_dcf, fixed on
   ASVspoof dev") visible. Real outcome, failures included.
5. (40 to 52 s) The October table, labelled "English ASVspoof proxy, simulated codecs": on held-out codecs the
   published SSL+AASIST is at 20.97% EER and the 8 kHz fine-tuned teacher at 21.63% (intervals overlap), with
   delta-NB -1.71 points and the best minDCF (0.381); at the dev FAR 1% threshold the published AASIST and
   AASIST-L reject 92 to 97% of genuine callers; the small CPU models sit at about 34% and distillation gave no
   gain. Indic: no claim (the pilot fails its duration-shortcut audit).
6. (52 to 60 s) "Built on Gnani Prisma + Timbre + voice cloning. Built with AI coding agents from my spec.
   Code + report in the thread. #GnaniAI #GreatIndianAIInternshipChallenge"

Recording tips:
- Win+Alt+R (Xbox Game Bar) records the active window. Settings > Gaming > Captures: 1080p, 30 fps, "record audio"
  on only if the Timbre prompt should be heard. Clipchamp (preinstalled) can also record the screen, and is the
  easiest editor: trim, add text, auto captions (Captions panel), export 1080p.
- Burn captions in: X and LinkedIn autoplay muted. Every number on screen as text, with "English proxy" or "my
  own voice, n = 15" next to it.
- Mask the key: never open `.env` in an editor or a terminal while recording, close VS Code, never run
  `Get-Content .env` or print `$env:GNANI_API_KEY`. The demo prints "key loaded (never shown)". Scrub through the
  recording before posting; if the key ever appears, rotate it and re-record.
- Show the operating point: keep the "CM: lcnn8_aug at min_dcf (tau_llr ..., fixed on ASVspoof dev)" line on
  screen while the decisions print, and caption it.
- Terminal: Windows Terminal, font size 18 to 20 (Ctrl and +), dark theme, window maximised.
