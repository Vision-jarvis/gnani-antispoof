# Recording kit: your own voice

Who records: you, the builder, and nobody else (consent `self` in `factory/manifests/demo_builder_voice.csv`).
When: a 2-minute **test recording on Oct 30** (never sent anywhere), then the **real takes on Sun Nov 1 at about
09:00** (about 15 minutes), plus one **live answer at about 18:00**. The file names and texts below are exactly what
the code reads (`factory/manifests/own_voice_takes.csv` is the source of truth; a unit test checks this page
against it).

## What happens to the recordings

| Step (Nov 1) | What is sent | Gnani calls |
|---|---|---|
| Clone (about 10:00) | `builder_15s` once to the voice-clone embeddings API; then the clone says the 15 answer texts below (text-matched to your takes) | 16 (1 embedding + 15 VC TTS: 10 as 16 kHz WAV, 5 straight to 8 kHz mu-law) |
| Prisma check (about 16:00) | `hinglish_01` to `hinglish_10` at 8 kHz, each to Prisma v2.5 and v3.0 | 20 STT REST calls |
| Live IVR (about 18:00) | the IVR prompt, `live_answer`, and the clone saying the same fresh phrase | 4 (1 Timbre + 1 VC TTS + 2 Prisma realtime sessions) |
| Total | | 40 calls, each run hard-capped; the price per call is unpublished, so read the credit balance on app.gnani.ai before and after |

- Your recordings stay on this laptop in `data/own_voice/` (git-ignored). Clone audio stays in
  `artifacts/gnani_cache/` (git-ignored). `.gitignore` also ignores every audio file type repo-wide. Only scores
  and decision codes are committed or posted; no audio, real or cloned, is ever published.
- Teacher scoring on Modal uploads the 8 kHz trial WAVs to your private Modal volume and deletes them right after
  (`docs/DEMO_RUNBOOK.md`); the CPU alternative uploads nothing.
- No personal data in any take: every phrase is fixed, the digits come from the IVR's own random generator, and
  nothing below is a real name, account or phone number. Do not add any.

## Setup (Windows 11)

1. Quiet room, door and window closed, fan, AC and music off. A room with curtains, a bed or a sofa echoes less
   than a bare one.
2. One microphone for every take (the laptop's built-in mic is fine). Sit so your mouth is about 15 to 20 cm from
   it, the distance of a phone at your ear, and speak at normal phone-call volume: no whispering, no shouting.
3. Settings > System > Sound > Input: pick that microphone, input volume about 70 to 80%. If you see "Audio
   enhancements" or "Voice clarity" (Windows Studio Effects), turn them off; if you cannot, keep them the same
   for every take.
4. Open **Sound Recorder** (Start, type "Sound Recorder"). In its "..." menu > Settings: recording format
   "AAC (.m4a)" (the default) or WAV, audio quality "High" or "Best", and the same microphone as above.
5. Level check: record "hello, testing" for 3 s and play it back. It should be clear, not distorted, not faint.
6. For each take: press record, wait half a second, say the text once, wait half a second, stop. Natural speech,
   as if answering a bank IVR on the phone; do not over-articulate. If you stumble, delete that take and redo it.
7. Sound Recorder saves to `Documents\Sound recordings` as "Recording (N).m4a". Rename each file to its take name
   (for example `answer_01.m4a`) and move it into the repo's `data\own_voice\raw\` folder (create it). Any of
   .m4a .wav .mp3 .aac .flac .ogg .opus .webm .wma works; one file per take.

Folder layout (all git-ignored):

```
data/own_voice/raw/<take>.m4a          what you record (Nov 1)
data/own_voice/16k/<take>.wav          written by scripts/prep_own_voice.py (mono, 16 kHz, -23 LUFS, silence trimmed)
data/own_voice/8k/<take>.wav           the same at 8 kHz
data/own_voice/builder_15s.wav         the reference the clone API gets (written by the prep script)
data/own_voice/trials/<codec>/{bona,spoof}/   genuine takes and clones through G.711 / AMR-NB (prep script, "trialsets")
data/own_voice/test/raw/<take>.m4a     the Oct 30 test recording (separate; never sent to any API)
```

## The takes

### 1. Reference: `builder_15s` (read once, about 15 to 20 s)

Read this passage naturally, at your normal pace. The prep script needs 5 to 30 s of speech (the clone API's
limit) and warns outside 12 to 20 s.

> आज सुबह मौसम बहुत सुहाना था। मैंने खिड़की खोली तो ठंडी हवा अंदर आई और पेड़ों पर चिड़ियाँ चहचहा रही थीं। मैंने एक कप चाय बनाई, थोड़ी देर किताब पढ़ी और फिर दिन भर के काम की सूची बनाई। शाम को पार्क में टहलने का मन है, और रात को जल्दी सोने का इरादा है।

*aaj subah mausam bahut suhaana tha. maine khidki kholi to thandi hawa andar aayi aur pedon par chidiyaan
chahchaha rahi thin. maine ek cup chai banaayi, thodi der kitaab padhi aur phir din bhar ke kaam ki soochi
banaayi. shaam ko park mein tahalne ka man hai, aur raat ko jaldi sone ka iraada hai.*

### 2. Genuine IVR answers: `answer_01` to `answer_05` (about 3 to 4 s each)

The IVR's own challenge format: four digits spoken as Hindi words, then the sentence (these are exactly the
challenges `ivr_demo` generates for seeds 101 to 105). Leave a short natural pause after the digits. "Test"
marks the Oct 30 subset.

| File | Say | Transliteration | Test |
|---|---|---|---|
| `answer_01` | तीन नौ छह तीन मेरी आवाज़ ही मेरी पहचान है | teen nau chhah teen, meri aawaaz hi meri pehchaan hai | yes |
| `answer_02` | चार एक पाँच पाँच मेरी आवाज़ ही मेरी पहचान है | chaar ek paanch paanch, meri aawaaz hi meri pehchaan hai | yes |
| `answer_03` | पाँच तीन शून्य दो मेरी आवाज़ ही मेरी पहचान है | paanch teen shoonya do, meri aawaaz hi meri pehchaan hai |  |
| `answer_04` | सात आठ तीन छह मेरी आवाज़ ही मेरी पहचान है | saat aath teen chhah, meri aawaaz hi meri pehchaan hai |  |
| `answer_05` | दो छह नौ नौ मेरी आवाज़ ही मेरी पहचान है | do chhah nau nau, meri aawaaz hi meri pehchaan hai |  |

### 3. Hinglish answers: `hinglish_01` to `hinglish_10` (about 3 to 4 s each)

Same format, with a Hinglish banking phrase: say the English words the way you normally would in Hinglish. They
are used twice: for the Prisma v2.5 vs v3.0 phrase-match comparison on 8 kHz audio (each answer goes to both
models), and as more genuine trials against their clones.

| File | Say | Transliteration | Test |
|---|---|---|---|
| `hinglish_01` | दो नौ एक पाँच मेरी voice ही मेरा password है | do nau ek paanch, meri voice hi mera password hai | yes |
| `hinglish_02` | एक तीन चार चार please मेरा account verify कीजिए | ek teen chaar chaar, please mera account verify kijiye | yes |
| `hinglish_03` | तीन सात नौ तीन मुझे अपना balance check करना है | teen saat nau teen, mujhe apna balance check karna hai |  |
| `hinglish_04` | सात पाँच आठ आठ मेरा OTP अभी तक नहीं आया | saat paanch aath aath, mera OTP abhi tak nahin aaya |  |
| `hinglish_05` | पाँच नौ पाँच दो card block करवाना है please | paanch nau paanch do, card block karwana hai please |  |
| `hinglish_06` | पाँच आठ छह तीन मेरी last transaction cancel कर दीजिए | paanch aath chhah teen, meri last transaction cancel kar dijiye |  |
| `hinglish_07` | एक दो दो चार मुझे new cheque book चाहिए | ek do do chaar, mujhe new cheque book chahiye |  |
| `hinglish_08` | आठ नौ आठ छह मेरा mobile number update करना है | aath nau aath chhah, mera mobile number update karna hai |  |
| `hinglish_09` | सात दो छह पाँच customer care से बात करनी है | saat do chhah paanch, customer care se baat karni hai |  |
| `hinglish_10` | दो सात छह छह मेरा loan EMI कब due है | do saat chhah chhah, mera loan EMI kab due hai |  |

### 4. Enrolment: `enrol` (about 8 to 12 s)

> यह मेरी आवाज़ का नमूना है। एक, दो, तीन, चार, पाँच, छह, सात, आठ, नौ, दस। आज का दिन अच्छा है।

*yah meri aawaaz ka namoona hai. ek, do, teen, chaar, paanch, chhah, saat, aath, nau, das. aaj ka din achchha hai.*

Only used if the live demo runs with `--asv lfcc` (the LFCC stand-in, which is not a speaker verifier); by
default the identity gate is bypassed and said so on screen.

### 5. Live answer: `live_answer` (Nov 1, about 18:00, recorded on the spot)

This one cannot be recorded in advance: the IVR makes up a fresh random phrase (that is what stops replay).
Step 1 of the live demo prints the phrase and saves the prompt to `artifacts/gnani_cache/ivr_prompt.wav`. Play
the prompt, record yourself saying exactly that phrase once, save it as `data/own_voice/raw/live_answer.m4a`,
then run `python scripts/prep_own_voice.py --only live_answer` (`docs/DEMO_RUNBOOK.md`, 18:00).

## Oct 30: the 2-minute test recording (no API calls)

Record only the six takes marked "Test" (`builder_15s`, `answer_01`, `answer_02`, `hinglish_01`, `hinglish_02`,
`enrol`) into `data\own_voice\test\raw\`, then in PowerShell from the repo folder:

```powershell
.\.venv\Scripts\python scripts\prep_own_voice.py --root data/own_voice/test --subset test
```

Expected: one line per take, "6 take(s) prepared", no ERROR line, exit code 0. Send the agent that printout (not
the audio); the agent then rehearses the whole Nov 1 run on these takes in mock mode. Test takes are never sent
to any API: the clone manifest points at `data/own_voice/builder_15s.wav`, not at the test folder. On Nov 1 you
record everything again into `data\own_voice\raw\`.

## Nov 1: convert

```powershell
.\.venv\Scripts\python scripts\prep_own_voice.py
```

Expected: 17 lines (every take except `live_answer`), "17 take(s) prepared", a reference line saying
`data/own_voice/builder_15s.wav`, exit code 0. Fix any ERROR before the clone step (the clone step refuses to send
a reference that is missing or outside 5 to 30 s).

| Message | What to do |
|---|---|
| `no recording at data/own_voice/raw/<take>.m4a` | the file is missing or still called "Recording (N).m4a": rename it |
| `several recordings found` | keep one file per take |
| `... s of speech after trimming silence; it must be ...` | re-record: say the whole phrase (reference: the whole passage) |
| `no speech found` | wrong or muted microphone; check step 3 of the setup |
| warning `clipping` | lower the input volume or move back a little, re-record |
| warning `very quiet` | move closer or raise the input volume, re-record |
| warning `source is 8000 Hz` | Sound Recorder quality is set low: choose High |
| `needs ffmpeg` | `winget install Gyan.FFmpeg` (already installed on this laptop) |

After the clone run, `python scripts/prep_own_voice.py trialsets` puts your 15 answers and their 15 clones through
G.711 and AMR-NB 4.75k into `data/own_voice/trials/` for the trials (runbook, 14:00).
