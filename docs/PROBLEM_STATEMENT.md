> This is the problem statement I wrote before any code existed (the "spec" the AI coding agents built to).
> It is kept as written, apart from removing outreach notes; where the build departs from it, README.md,
> STATUS.md and REPORT.md say so. Freshness notes at the top were added as the field moved.

# Gnani.ai: Catching Indic voice clones on an 8 kHz phone line (telephony-native anti-spoofing for Armour365)

*Freshness check 2026-10-29: Prisma v3.0 STT released as opt-in (docs changelog 2026-10-22, announced 2026-10-28); the build stays on Prisma v2.5 (a qualifying challenge model) with an optional `model=prisma-v3.0` phrase-check run. RealComm (arXiv:2610.27459, 2026-10-20) and arXiv:2610.07216 (2026-10-05) added as related work. Challenge page (checked 2026-10-29): shortlist decided by verified engagement by the deadline, the demo post must be nominated via the submission form, contributions documented, Crowd Favourite award; demo to be posted Nov 3-5. Smallest.ai 15 s cloner (2026-10-28) added to the unseen-cloner list.*

*Freshness check 2026-10-23: official `gnani-vachana` SDK (PyPI) added to resources; arXiv:2609.39651 and arXiv:2609.09489 added as related work.*

> Build a streaming voice anti-spoofing countermeasure that detects TTS clones, voice conversion and replay **after** the audio has been squeezed through 8 kHz narrowband codecs (G.711, AMR-NB, GSM, Opus), stays accurate on Indian-language clones made by commercial cloners it has never seen (including Gnani's own voice-cloning API), and decides within 2 seconds of caller speech, wrapped in a working IVR voice-auth flow built on Gnani Prisma STT and Timbre TTS.

**Company:** Gnani.ai (Gnani Innovations Pvt Ltd), Bengaluru, voice-AI platform, Series B (first close March 2026) | **Context:** written for the Great Indian AI Internship Challenge (deadline Nov 10, 2026, 11:59 PM IST)

---

## 1. About the company

Gnani.ai builds a fully in-house voice stack for Indian languages: speech recognition, speech synthesis, voice cloning, an LLM, and a speech-to-speech model. Verified numbers:

- Founded 2016 by co-founders Ganesh Gopalan (CEO) and Ananth Nagaraj. Raised $10M from Aavishkaar Capital as the first close of its Series B (announced 31 March 2026), with Info Edge Ventures participating. FY25 revenue Rs 53.87 crore (up from Rs 23.09 crore), net profit Rs 3.19 crore. The company says it processes **over 30 million voice interactions daily across 12+ languages for 200+ enterprise clients, including banks and insurers**, and has a proprietary 14B-parameter speech-to-speech model ([Business Today, 31 Mar 2026](https://www.businesstoday.in/amp/technology/story/gnaniai-raises-10-million-in-funding-from-aavishkaar-capital-to-scale-global-voice-ai-push-523218-2026-03-31)).
- **Public developer APIs** at `https://api.vachana.ai` ([docs](https://docs.gnani.ai/api/introduction/introduction.md)): **Gnani Prisma v2.5** STT (REST up to 60 s, realtime WebSocket that accepts 8000 Hz "narrowband telephony (legacy PSTN / VoIP)" audio, batch), **Gnani Timbre v2.5 / v3.0** TTS in 10 languages (Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Punjabi, Bengali, Gujarati) with output containers that include raw G.711 `mulaw` / `alaw` (forced 8000 Hz) and OGG Opus ([TTS REST](https://docs.gnani.ai/api/TTS/tts-inference.md)), and a **voice-cloning API**: upload 5 to 30 s of reference audio, receive a `[1, 768]` speaker embedding, then synthesize any text in that voice with model `vachana-vc-v1` at 8,000 to 44,100 Hz ([Voice Clone Embeddings](https://docs.gnani.ai/api/VC/voice-clone-embeddings.md), [Voice Cloned TTS](https://docs.gnani.ai/api/VC/vc-inference.md)).
- **Armour365**, Gnani's voice biometrics product. Its public API ([GitHub: Gnani-AI/voicebiometric-api-armour365](https://github.com/Gnani-AI/voicebiometric-api-armour365)) exposes decision codes `0 = Success`, `1 = Spoof Failure`, `2 = Voice Failure`, `3 = Internal Error`, an anti-spoofing layer returning `Bonafide (0) / Spoof (1)`, and a 7-second minimum for enrolment audio.

Why this problem sits at the centre: Gnani sells both sides of the same technology. Its Timbre and voice-cloning APIs make convincing Indic cloned speech cheap. Its Armour365 customers (banks, contact centres) need to know that a caller saying the passphrase is a live human and not one of those clones. Every gain in Gnani's TTS quality raises the bar its own anti-spoofing has to clear.

## 2. The problem

**Gnani's own framing.** In "Deepfake Detection in Voice Biometrics: How Enterprise Systems Catch Cloned Voices" (Gnani blog, 4 May 2026, [link](https://gnani.ai/resources/blogs/voice-biometrics-how-armour-detects-spoofs-and-deepfakes)), Gnani lists four attacks Armour365 must stop: **replay** ("a genuine recording of the customer is played down the line"), **synthetic clone** ("a TTS or voice cloning model generates new speech from a short sample"), **mimicry**, and **injection** ("generated audio is fed straight into the call stream, bypassing the microphone"). It claims a "99%+ fraud detection rate and identity verification in under 5 seconds", and adds the honest caveat this problem is built on: *"Detection performance depends on sample rate, codec, noise, call length and which generation tool produced the attack."*

**A concrete attack.** A bank's IVR uses voice biometrics to let customers reset a card PIN or raise a UPI limit without an agent. The fraudster has 20 seconds of the customer speaking Kannada, taken from a WhatsApp voice note forwarded to a family group. Today any public cloning API (Gnani's included: 5 to 30 s of reference is enough) turns that into a voice embedding. The fraudster calls from a prepaid SIM. The IVR, speaking in Timbre's voice, says *"Please say: nanna dhwani nanna guruthu"* ("my voice is my identity" in Kannada). The fraudster types the phrase into a realtime cloned-TTS WebSocket and plays the output into the call, or injects it through a softphone. The speaker-verification score is high, because the clone was built to match the voiceprint. The only defence left is the anti-spoofing layer, and it has to decide on **about 2 seconds of 8 kHz G.711 or AMR-NB audio**, with the 4 to 8 kHz band (where most vocoder artefacts live) already removed by the phone network.

**Business cost.**
- A *false accept* is an account takeover in a bank's own authenticated channel. The bank carries the loss and the reputational damage, and the biometrics vendor loses the account.
- A *false reject* pushes a real customer to an agent queue. That cancels the handle-time saving that justified buying voice biometrics in the first place, and contact centres measure it every month.
- Regulators and bank CISOs now ask vendors directly about deepfakes. A vendor that can show per-codec, per-language, unseen-generator error rates (not one "99%" number) wins the security review.

**Why not just reuse the academic SOTA.** ASVspoof models are trained on 16 kHz English read speech (VCTK-derived), and their most-cited numbers come from clean audio. The candidate problem in the research dossier was confirmed as genuine and is kept. Gnani's own blog names codec, sample rate and generation tool as the variables that matter. The dossier's alternative (streaming speech-to-speech latency) is a real problem too, but it needs Gnani's internal models. Anti-spoofing can be built and benchmarked honestly on public data plus Gnani's public APIs.

## 3. Why it is hard

**3.1 The phone network deletes the evidence.** In the ASVspoof 2021 LA task, bona fide and spoofed speech was sent over real VoIP (Asterisk PBX) and PSTN links in seven conditions: none, a-law 8 kHz, PSTN + mu-law 8 kHz, G.722 16 kHz, mu-law 8 kHz, GSM 8 kHz at 13 kbps, Opus 16 kHz. The organisers report that, for the top-10 systems, error was higher on the **narrowband conditions (a-law, PSTN, mu-law, GSM) than the wideband ones**, "indicating the general importance of information at higher frequencies to CM performance", and that among narrowband conditions **lower bitrate and uncontrolled transmission (GSM, PSTN) were worst** ([Liu et al., ASVspoof 2021 summary, IEEE/ACM TASLP, arXiv:2210.02437](https://arxiv.org/abs/2210.02437)). Example: a HiFi-GAN vocoder leaves periodic high-frequency ripple near 6 to 7 kHz. After 8 kHz resampling plus G.711 that band no longer exists, so a detector that learned "ripple = fake" now sees only quantisation noise, and it sees that noise on real and fake audio alike.

**3.2 The attacker can synthesize straight into the codec.** Gnani's Timbre endpoint returns `container=mulaw` at a forced 8000 Hz. A clone produced natively at 8 kHz never had a wideband artefact to lose, and training-time "simulate the phone channel on a 16 kHz fake" augmentation does not cover it. A good test set needs both *studio-fake then channel* and *born-narrowband* fakes, and the two behave differently.

**3.3 Unseen generators and unseen languages.** In the ASVspoof 2021 DF task, many systems scored under 10% EER on the progress subset (the best under 1%), yet **all exceeded 15% EER on the evaluation subset**, because of unseen compression and source data (same paper). Müller et al. found that ASVspoof-trained models suffer "performance degradation of up to one thousand percent" on real-world deepfakes ([Does Audio Deepfake Detection Generalize?, Interspeech 2022, arXiv:2203.16263](https://arxiv.org/abs/2203.16263)). IndicSynth (ACL 2025) was created because detectors trained on one language lose accuracy on others ([ACL Anthology 2025.acl-long.1070](https://aclanthology.org/2025.acl-long.1070)). A Hindi clone from a commercial Indic cloner is unseen on three axes at once: generator, language, channel. Recent related work attacks the same robustness gap from two directions: a neural-codec approach to robust deepfake detection ([arXiv:2609.39651](https://arxiv.org/abs/2609.39651)) and temporal-coherence cues ([arXiv:2609.09489](https://arxiv.org/abs/2609.09489)); both are candidate comparisons for the channel-robustness results here.

**3.4 Shortcut features look like accuracy.** On ASVspoof 2019/2021, "bonafide instances tend to have significantly longer leading and trailing silences than spoofed instances". A classifier using *only* silence duration reaches 15.1% EER, and trimming silence pushed a signal model from 3.6% to 15.5% EER ([Müller et al., "Speech is Silver, Silence is Golden", arXiv:2106.12914](https://arxiv.org/abs/2106.12914)). An Indic clone set built carelessly has the same trap in new forms: bona fide from one corpus (one mic, one loudness, one text style) and spoofs from an API (different loudness, perfect pauses). The model learns "corpus", not "spoof".

**3.5 Replay and injection are different physics.** Replay adds a loudspeaker and a room, then a phone mic, then the codec, so a bona fide signal is re-recorded. Injection adds nothing acoustic at all. A detector tuned only on TTS/VC artefacts misses replay. A detector tuned on "room-ness" flags real callers on speakerphone in a noisy auto-rickshaw.

**3.6 Latency and cost.** The decision has to arrive inside an IVR turn (target: 2 s of speech plus under 300 ms compute), running alongside STT and speaker verification, for millions of calls. The SOTA SSL front-end (wav2vec 2.0 XLS-R, 300M parameters) is accurate but expensive per stream. The lightweight AASIST-L (85,306 parameters) is cheap but was built and scored on clean 16 kHz audio.

## 4. What you must build

### Part A: IndicClone-Tel, an attack and channel factory
1. **Bona fide pool:** Indian-language read speech from Kathbath (HF card metadata says CC-BY-4.0, its text says CC0; cite the HF page), at least 4 languages (Hindi, Kannada, Tamil, Bengali suggested), speaker-disjoint train/dev/eval splits.
2. **Spoof generators** (each tagged with an attack ID):
   - G1: Gnani **Timbre v2.5/v3.0** stock voices reading the same transcripts (TTS, no target).
   - G2: Gnani **voice-cloning API** (`vachana-vc-v1`): clone only consenting speakers (today: the builder's own voice; later friends with written consent) from 5 to 30 s of reference, synthesize *different* sentences. Cloning Kathbath corpus speakers is **DEFERRED** until Gnani confirms in writing that cloning public-corpus speakers for anti-spoof evaluation is allowed (corpus licences do not cover voice likeness).
   - G3: Born-narrowband variants of G1/G2 requested directly as `container=mulaw` / `alaw`.
   - G4: Open-source clones (XTTS-v2 / VITS / FreeVC samples from IndicSynth).
   - Unseen commercial cloners for the held-out set also include Smallest.ai, which advertises cloning from 15 s of audio, "ready in under a minute" (2026-10-28, https://x.com/smallest_AI/status/2115446291421708521). Same consent rules as G2.
   - G5: Replay simulation: bona fide played through a loudspeaker impulse response, re-captured with a phone-mic response and room reverb, then put through the channel.
   - G6: Injection: G2 audio sent straight to the channel with no acoustic path.
3. **Channel simulator** (applied identically to bona fide and spoof): 8 kHz resample; G.711 mu/A-law; AMR-NB at 4.75 / 7.95 / 12.2 kbps; AMR-WB 12.65 kbps then down to 8 kHz; Opus 6 to 16 kbps; GSM-FR; 0 to 5% packet loss with concealment; two-hop transcoding chains (for example AMR-NB to G.711, imitating mobile to PSTN to contact centre).
4. **Anti-shortcut normalisation:** VAD-trim *all* audio to the same leading/trailing silence policy, apply the same loudness normalisation (LUFS target), and match the text distribution per language between bona fide and spoof.

### Part B: Telephony-native countermeasure (CM)
- Input: 8 kHz mono audio (any length, at least 1 s). Output: a calibrated log-likelihood-ratio score (bona fide vs spoof) plus an attack-family guess (TTS/VC, replay, injection).
- Teacher: SSL front-end (XLS-R 300M or WavLM) plus AASIST back-end, fine-tuned at 8 kHz with codec augmentation (Part A simulator) and RawBoost.
- Student: under 5M parameters, distilled from the teacher, which must run on CPU.
- **Streaming:** emit a score after 1.0 s, 2.0 s and 4.0 s of speech, with each decision using only audio up to that point.

### Part C: Voice-auth IVR flow (also the Gnani challenge entry)
1. Timbre speaks a **randomised challenge phrase** (random digits plus a short sentence) in the caller's language, at 8 kHz.
2. The caller replies. **Prisma v2.5 realtime STT at 8000 Hz** transcribes it, and the phrase must match (normalised edit distance under a set threshold). This defeats replay of old recordings. Optional (freshness check 2026-10-29): repeat the phrase check with `model=prisma-v3.0`, Gnani's new opt-in STT (one model for 9 Indian languages + English, `indic-auto` language ID, 8 kHz and 16 kHz input; Prisma v2.5 stays the default on REST and Realtime; docs changelog 2026-10-22, https://docs.gnani.ai/changelog , https://docs.gnani.ai/api/STT/models/prisma-v3.md ; announced 2026-10-28, https://x.com/GnaniAi/status/2115337828699943189). Keep v2.5 as the submitted path, because the challenge page still names Prisma v2.5 / Timbre v2.5 / Evon v3.3 as the qualifying models, and report the v3.0 run separately.
3. The CM (Part B) scores liveness. An open-source speaker-verification model (for example SpeechBrain ECAPA) stands in for Armour365 matching.
4. The fused decision is returned using **Armour365's decision codes** (`0` success, `1` spoof, `2` voice failure) so the module could slot into Gnani's API shape.
5. The red-team mode runs the G2 realtime cloned-TTS attack against the flow live and logs the time from prompt to response.

**In scope:** logical access (TTS, VC, injection) and simulated replay over narrowband channels. **Out of scope:** adversarial (gradient) attacks, mimicry by humans, real PSTN calls. Closest new work on that gap: **RealComm** (arXiv:2610.27459, 2026-10-20, https://arxiv.org/abs/2610.27459) pairs digital speech with the same utterances sent through real mobile calls (acoustic and wired injection, handset and speakerphone, caller-side denoising) and shows detectors degrade badly after call transmission (RealComm-Aug plus real-call training cuts one detector's EER from 37.94% to 22.37%). If access is granted, evaluate on RealCommBench and compare `channel_sim.py` with RealComm-Aug. RealComm is not Indic, so the Indic-clone gap still stands.

### Honesty rules (violations void the result)
1. **Speaker-disjoint, text-disjoint, attack-disjoint eval.** G2 (Gnani cloner) and G3 are **never** used in training; they are the "unseen commercial Indic cloner" test. Report seen and unseen generators separately.
2. **Held-out codecs:** AMR-NB 4.75 kbps, GSM-FR and two-hop chains are eval-only.
3. **No metadata at inference:** no file names, durations, corpus IDs, language labels, or codec labels as inputs. Score from the waveform only.
4. **Silence-shortcut audit:** report EER of a silence-duration-only classifier and a loudness-only classifier on your eval set. If either beats 35% EER, fix the data before reporting.
5. **Causality:** the streaming score at time t uses only samples up to t. No look-ahead padding beyond 200 ms.
6. **Thresholds fixed on dev** and never retuned on eval.
7. **Synthetic data only, no clone leakage:** no real phone numbers, account data or recorded calls (a challenge rule too). No cloned clip of any person is published (scores and the generator script only). Clones are made only of the builder's own voice (and consenting friends); Kathbath-speaker cloning is DEFERRED pending Gnani's written answer.
8. **Compute budget:** the teacher's fine-tuning stays within $50 of cloud GPU. Report GPU-hours.

## 5. Data, services and resources

| Resource | Link | Licence (as shown) | Use |
|---|---|---|---|
| ASVspoof 2019 (LA.zip 7.12 GB, TTS/VC/replay) | [Edinburgh DataShare 10283/3336](https://datashare.ed.ac.uk/handle/10283/3336) | Open Data Commons Attribution | Train (English, A01-A19 attacks) |
| ASVspoof 2021 LA eval (7.8 GB, real VoIP/PSTN codecs) | [Zenodo 4837263](https://zenodo.org/records/4837263), keys at [asvspoof-challenge/2021](https://github.com/asvspoof-challenge/2021) | ODC-By v1.0 | Real-channel benchmark |
| ASVspoof 2021 DF eval | [Zenodo 4835108](https://zenodo.org/records/4835108) | ODC-By v1.0 (per 2021 release) | Compression benchmark (stretch) |
| ASVspoof 5 (~2,000 speakers, 32 attack algorithms, 142.3 GB) | [Zenodo 14498691](https://zenodo.org/records/14498691), paper [arXiv:2502.08857](https://arxiv.org/abs/2502.08857) | ODC-By v1.0 | Optional extra training subset |
| In-the-Wild (37.9 h, 58 public figures) | [HF mueller91/In-The-Wild](https://huggingface.co/datasets/mueller91/In-The-Wild) | CC-BY-SA-4.0 | Out-of-domain eval |
| MLAAD (54 languages, 205 TTS models, 1,153.6 h) | [HF mueller91/MLAAD](https://huggingface.co/datasets/mueller91/MLAAD), [arXiv:2401.09512](https://arxiv.org/abs/2401.09512) | CC-BY-NC 4.0 | Multilingual spoof training |
| IndicSynth (4,000+ h, 12 Indian languages, XTTS-v2/VITS/FreeVC) | [HF vdivyasharma/IndicSynth](https://huggingface.co/datasets/vdivyasharma/IndicSynth) (845 GB, so subsample) | CC-BY-NC 4.0 | G4 attacks |
| Kathbath (1,684 h, 12 languages, 1,218 speakers) | [HF ai4bharat/Kathbath](https://huggingface.co/datasets/ai4bharat/Kathbath) (gated: accept terms) | CC0 | Bona fide Indic + clone references |
| RawBoost augmentation | [arXiv:2111.04433](https://arxiv.org/abs/2111.04433) (ICASSP 2022) | code on GitHub | Channel augmentation |
| Gnani Prisma v2.5 / Timbre / Voice cloning | [docs.gnani.ai](https://docs.gnani.ai/api/introduction/introduction.md) | challenge credits | Attacks + IVR flow |
| Official Gnani Python SDK `gnani-vachana` | [PyPI gnani-vachana](https://pypi.org/project/gnani-vachana/) | see PyPI page | Use for Gnani API calls instead of hand-rolled HTTP/WebSocket clients |

Notes. MLAAD and IndicSynth are **non-commercial**: fine for a research prototype and a challenge entry, but a production Armour365 model would need Gnani's own licensed data. The report must say so. Codec simulation uses ffmpeg (`pcm_mulaw`, `pcm_alaw`, `libopencore_amrnb`, `libopus`, `gsm`); AMR-NB needs an ffmpeg build with opencore-amr.

**Gnani credit budget.** Each registrant gets 5,000 programme credits ([gnani.ai/internship](https://www.gnani.ai/internship)). The credit cost per TTS character / VC call is not published (unverified), so measure it on 10 calls on Day 1 and size G1/G2 from that. Target about 1,500 Gnani-generated clips (around 2 h); cache everything.

## 6. Interfaces and constraints

```
POST /v1/cm/score            (multipart: audio=8 kHz mono WAV/mulaw/alaw/AMR)
-> {"llr": -3.41, "p_spoof": 0.93, "family": "tts_vc",
    "partial": [{"t":1.0,"llr":-1.2},{"t":2.0,"llr":-3.4}], "rtf": 0.018}

WS  /v1/cm/stream            (20 ms frames of 8 kHz PCM16 or mulaw)
-> {"t": 2.0, "llr": -3.4, "decision": "spoof"}   emitted at 1 s, 2 s, 4 s

POST /v1/auth/verify          (IVR flow, Part C)
-> {"StatusCode":0, "DecisionCode":1, "phrase_match":true,
    "asv_score":0.81, "cm_llr":-3.4, "latency_ms":240}
```

| Constraint | Budget |
|---|---|
| Decision horizon | at most 2.0 s of caller speech for the primary decision |
| Student CM compute | RTF at most 0.05 on one laptop CPU core (8 kHz input), peak RAM at most 200 MB |
| Student size | under 5M parameters (ONNX export required) |
| Teacher | any size, offline scoring only |
| End-to-end flow latency | at most 300 ms from end of speech to decision, excluding Prisma network time (reported separately) |
| Cloud spend | at most $50 GPU, at most 5,000 Gnani credits |

## 7. Evaluation

**Definitions.** For CM threshold tau: FAR(tau) = spoofs accepted / spoofs; FRR(tau) = bona fide rejected / bona fide. **EER** = the point where FAR = FRR (via ROC convex hull).
- **minDCF** = min over tau of [C_miss * (1 - pi_spf) * FRR(tau) + C_fa * pi_spf * FAR(tau)] / min(C_miss * (1 - pi_spf), C_fa * pi_spf), with pi_spf = 0.05, C_miss = 1, C_fa = 10 (a bank-style prior; state the parameters with every number).
- **FRR@FAR1** = FRR at the dev-set threshold giving FAR = 1%, applied unchanged to eval (so it measures calibration drift too).
- **Narrowband penalty** delta-NB = EER(8 kHz codec pool) - EER(clean 16 kHz pool), on the same utterances.
- **Unseen-Indic EER** = EER on {Kathbath bona fide} vs {G2 + G3 Gnani clones}, after the channel.
- **Cllr** (calibration cost of the LLR scores).
- **End-to-end attack success rate (ASR)** of the Part C flow: share of G2/G5/G6 attacks that receive `DecisionCode = 0`, and genuine-user success rate on bona fide trials.

**Baselines to beat** (run all of them on IndicClone-Tel eval yourself; published numbers are for reference only):

| Baseline | Published result | Source |
|---|---|---|
| LFCC-LCNN (ASVspoof 2021 B03) | 9.26% EER, min t-DCF 0.3445 on 2021 LA | ASVspoof 2021 summary, Table VIII |
| RawNet2 (B04) | 9.50% EER on 2021 LA; 22.38% on 2021 DF | same |
| AASIST / AASIST-L (pretrained) | 0.83% / 0.99% EER on 2019 LA (clean) | [clovaai/aasist](https://github.com/clovaai/aasist), [arXiv:2110.01200](https://arxiv.org/abs/2110.01200) |
| wav2vec 2.0 XLS-R + AASIST + RawBoost (pretrained LA model) | 0.82% EER (min t-DCF 0.2066) on 2021 LA; 2.85% on 2021 DF | [TakHemlata/SSL_Anti-spoofing](https://github.com/TakHemlata/SSL_Anti-spoofing), [arXiv:2202.12233](https://arxiv.org/abs/2202.12233) |
| Best 2021 LA challenge entry (T23) | 1.32% EER | ASVspoof 2021 summary |

Hypothesis to test, not assume: pretrained AASIST degrades sharply on 8 kHz AMR-NB Indic clones, and the SSL model degrades less but still misses born-narrowband Gnani clones.

**Reporting:** a table with EER / minDCF per (generator x codec x language) cell; DET curves for seen vs unseen generators; streaming EER at 1 s / 2 s / 4 s; the shortcut-audit results; an ablation (no codec augmentation, no RawBoost, 16 kHz vs 8 kHz-native front-end, teacher vs student); 10 annotated failure cases with spectrograms.

**Points (100):**

| KPI | Points |
|---|---|
| Unseen-Indic EER (G2+G3 after channel), lower is better, relative to best baseline | 25 |
| Pooled narrowband EER and delta-NB across held-out codecs | 15 |
| FRR@FAR1 with dev-fixed threshold (calibration honesty) | 10 |
| Streaming: EER at 2.0 s horizon | 10 |
| Student efficiency: RTF, params, RAM inside budget (0 if over) | 10 |
| End-to-end flow: attack success rate at most 5% with genuine success at least 90% | 10 |
| Replay / injection family detection (G5, G6 EER) | 5 |
| Rigor: shortcut audit, ablations, failure analysis, In-the-Wild / 2021 LA sanity check | 10 |
| Reproducibility: one-command eval, model card, data card | 5 |

## 8. Deliverables

```
gnani-armour-cm/
  factory/        # Part A: gnani_clone.py (Timbre + VC API), channel_sim.py, normalise.py, manifests/
  cm/             # Part B: teacher/, student/, train.py, distil.py, export_onnx.py
  service/        # FastAPI /v1/cm/score, WS /v1/cm/stream, /v1/auth/verify
  ivr_demo/       # Part C: Prisma realtime STT + Timbre prompts + CM + ECAPA, red-team mode
  eval/           # metrics.py (EER, minDCF, Cllr, FRR@FAR), shortcut_audit.py, report.ipynb
  REPORT.md  MODEL_CARD.md  DATA_CARD.md
```

- **5-minute check for Gnani engineers:** `make demo` downloads the ONNX student plus 200 eval clips, scores them, prints the per-codec EER table and starts the IVR demo on localhost with their own `X-API-Key-ID`.
- A 2-page report with the headline table, DET curves and honest limitations (non-commercial training data, simulated channels, no real PSTN).
- **Great Indian AI Internship Challenge requirements** (verified at [gnani.ai/internship](https://www.gnani.ai/internship); also reported by [FintechBizNews](https://fintechbiznews.com/fintech-technology/great-indian-ai-internship-challenge-by-gnani-ai)):
  - Deadline **10 November 2026, 11:59 PM IST**. Internships start 1 January 2027 (6 months, stipend up to Rs 1 lakh/month, up to 100 offers).
  - Eligible: enrolled at an Indian college/university, 18+, solo or a team of two.
  - Must use **at least one of Prisma v2.5 (STT), Timbre v2.5 (TTS), Evon v3.3 (LLM)**. This build uses Prisma (realtime 8 kHz phrase verification) and Timbre (prompts plus G1 attacks), with the voice-cloning API for G2/G3. Document each call in the write-up.
  - Submission: (1) a demo video, publicly posted; (2) a LinkedIn and/or X post with **#GnaniAI** and **#GreatIndianAIInternshipChallenge**, posted before submission; (3) a written explanation (problem, users, contributions); (4) a list of the Gnani models/APIs used.
  - Shortlist and nomination (page checked 2026-10-29, https://www.gnani.ai/internship): the **shortlist is decided by verified engagement (reactions, comments, reshares) recorded by the deadline**; the demo post must be **nominated via the submission form** (tagging alone does not enter it); each team member's contribution must be documented; there is also a **Crowd Favourite** award. Not confirmed whether this text is new or was missed on 2026-10-23. Consequence: post the demo early (Nov 3-5) so engagement accrues before Nov 10, and nominate it in the form the same day.
  - Data rule: no real phone numbers, account numbers, Aadhaar/PAN or recorded calls; use synthetic data only. No bought engagement.
  - Award fit: **Noise Canceller** (telephony audio performance), **Main Character** (regional language), **Solo Ninja**, **Demo Day Drop** (60-second video). Only one award per entrant.

## 9. The 3-day cut (~25 solo hours, laptop + at most $50 GPU)

**Day 1 (9 h): data and "the baseline breaks"**
- Register for challenge credits; measure credit cost per call. Pull ASVspoof 2019 LA, 2021 LA eval plus keys, Kathbath Hindi + Kannada (about 3 h each), and an IndicSynth Hindi/Kannada slice.
- `gnani_clone.py`: 300 Timbre stock-voice clips (G1) with a third requested as `mulaw` (G3), plus G2/G3 of the builder's own consented 15 s recording (16 calls). The 40-speaker Kathbath G2 plan is DEFERRED (consent, see Part A).
- `channel_sim.py` with 8 codec conditions plus 2 transcoding chains; normalisation and silence audit.
- Run pretrained AASIST, AASIST-L and SSL+AASIST on IndicClone-Tel.

**Day 2 (9 h): train the telephony-native CM**
- Rent one A100/L40S (about 10 to 12 h, roughly $15 to 25). Fine-tune XLS-R 300M + AASIST at 8 kHz on ASVspoof 2019 LA + MLAAD/IndicSynth subsets + Kathbath bona fide, with on-the-fly codec augmentation and RawBoost. G2/G3 and the held-out codecs stay untouched.
- Distil to a small 8 kHz student (an AASIST-L-sized raw-waveform model or a WavLM-small head); train streaming with random 1 to 4 s crops. Export ONNX and measure RTF on a laptop CPU.
- Full eval grid, ablation (with vs without codec augmentation), DET curves.

**Day 3 (7 h): product and story**
- FastAPI service plus WebSocket streaming. IVR demo: Timbre prompt in Kannada/Hindi, then Prisma 8 kHz realtime phrase check, then CM, then ECAPA, giving an Armour365-style decision code.
- Red-team run: the builder's own voice cloned through the Gnani VC API and attacked live; report end-to-end attack success.
- REPORT.md, model/data cards, 60-second video, challenge submission and X/LinkedIn post.

**Deferred:** real PSTN capture, adversarial attacks, ASVspoof 5 full training, Evon-based phrase generation, the SASV joint metric.

**60-second demo shot list**
1. (0-6 s) Text on screen: "A bank IVR. A Kannada caller. 20 seconds of WhatsApp audio is all a fraudster needs."
2. (6-15 s) Builder records 15 s, Gnani VC API clones it; the clone says the passphrase. Play both. They sound alike.
3. (15-25 s) Both go through G.711 / AMR-NB. Show the measured pretrained-SOTA score for each (whatever it is; only after the GPU scoring job has run).
4. (25-40 s) Live IVR at a named operating point shown on screen: Timbre prompts a random phrase; the real builder answers, then the clone answers. Show the real DecisionCodes and latency, including failures (unscripted; the challenge disqualifies misleading demos).
5. (40-52 s) Headline table: unseen Gnani-clone EER, baseline vs ours, per codec; streaming EER at 2 s; RTF on a laptop CPU.
6. (52-60 s) "Built on Gnani Prisma + Timbre. Code + report in the thread. #GnaniAI #GreatIndianAIInternshipChallenge"

## 10. Stretch goals
- Score on real Asterisk/SIP loops (the ASVspoof 2021 recipe) and on 2021 DF.
- SASV fusion: jointly calibrate CM + ASV, and report SASV-EER on ASVspoof 5.
- Generator attribution (Gnani VC vs XTTS vs FreeVC) for fraud forensics.
- Continual learning: a weekly "new cloner" drop with a fixed rehearsal budget, measuring forgetting.
- Evon v3.3 to generate diverse, phonetically balanced challenge phrases in all 10 languages.
- Code-mixed (Hinglish) clones and noisy-car / speakerphone bona fide to bring FRR down.
- INT8 quantisation and a calls-per-core density estimate for a contact-centre server.

## Sources
- Business Today, Gnani $10M Series B first close (31 Mar 2026): https://www.businesstoday.in/amp/technology/story/gnaniai-raises-10-million-in-funding-from-aavishkaar-capital-to-scale-global-voice-ai-push-523218-2026-03-31
- Gnani blog, "Deepfake Detection in Voice Biometrics" (4 May 2026): https://gnani.ai/resources/blogs/voice-biometrics-how-armour-detects-spoofs-and-deepfakes
- Armour365 API repo: https://github.com/Gnani-AI/voicebiometric-api-armour365
- Gnani Speech API docs: https://docs.gnani.ai/api/introduction/introduction.md ; TTS: https://docs.gnani.ai/api/TTS/tts-inference.md ; STT realtime: https://docs.gnani.ai/api/STT/stt-websocket.md ; Voice cloning: https://docs.gnani.ai/api/VC/voice-clone-embeddings.md , https://docs.gnani.ai/api/VC/vc-inference.md
- Great Indian AI Internship Challenge: https://www.gnani.ai/internship ; https://fintechbiznews.com/fintech-technology/great-indian-ai-internship-challenge-by-gnani-ai
- Liu et al., ASVspoof 2021 summary (IEEE/ACM TASLP): https://arxiv.org/abs/2210.02437
- Jung et al., AASIST: https://arxiv.org/abs/2110.01200 ; code: https://github.com/clovaai/aasist
- Tak et al., wav2vec 2.0 + data augmentation (Odyssey 2022): https://arxiv.org/abs/2202.12233 ; code: https://github.com/TakHemlata/SSL_Anti-spoofing
- Tak et al., RawBoost (ICASSP 2022): https://arxiv.org/abs/2111.04433
- Müller et al., Does Audio Deepfake Detection Generalize? (Interspeech 2022): https://arxiv.org/abs/2203.16263
- Müller et al., Speech is Silver, Silence is Golden: https://arxiv.org/abs/2106.12914
- Müller et al., MLAAD: https://arxiv.org/abs/2401.09512
- ASVspoof 5 paper: https://arxiv.org/abs/2502.08857 ; data: https://zenodo.org/records/14498691
- ASVspoof 2019: https://datashare.ed.ac.uk/handle/10283/3336 ; ASVspoof 2021 LA: https://zenodo.org/records/4837263 ; baselines/keys: https://github.com/asvspoof-challenge/2021
- In-the-Wild: https://huggingface.co/datasets/mueller91/In-The-Wild ; MLAAD: https://huggingface.co/datasets/mueller91/MLAAD
- IndicSynth: https://aclanthology.org/2025.acl-long.1070 ; https://huggingface.co/datasets/vdivyasharma/IndicSynth
- Kathbath: https://huggingface.co/datasets/ai4bharat/Kathbath
- Official Gnani SDK `gnani-vachana` (PyPI, checked 2026-10-23): https://pypi.org/project/gnani-vachana/
- Prisma v3.0 (opt-in, docs 2026-10-22, announced 2026-10-28): https://docs.gnani.ai/changelog ; https://docs.gnani.ai/api/STT/models/prisma-v3.md ; https://x.com/GnaniAi/status/2115337828699943189
- Related work: https://arxiv.org/abs/2609.39651 (neural codec for robust deepfake detection) ; https://arxiv.org/abs/2610.07216 (2026-10-05, neural-codec vulnerabilities: SOTA detectors misclassify legitimately codec-compressed bona fide speech as fake; relevant to the Opus and neural-codec conditions) ; https://arxiv.org/abs/2610.27459 (RealComm, 2026-10-20, real mobile-call transmission) ; https://arxiv.org/abs/2609.09489 (temporal coherence) ; Gnani's own Evon paper: https://arxiv.org/abs/2610.15371

