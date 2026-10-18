> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Available Voices

> Voice catalogs for Gnani Timbre v2.5 and Timbre v3.0.

## Available Voices

Each TTS model has its **own voice catalog**. Pick a model first, then choose a voice from that model's list.

| Model | `model` value | Voices | Languages per voice | Audio tags | Catalog |
| :- | :- | :- | :- | :- | :- |
| Timbre v3.0 | `timbre-v3.0` | 13 | All 10 languages | [Yes](/api/TTS/tts-audio-tags) | [Timbre v3.0 voices](#timbre-v3-0-voices) |
| Timbre v2.5 | `timbre-v2.5` | 42 | One preferred language each | — | [Timbre v2.5 voices](#timbre-v2-5-voices) |

<Warning>
  Voices are not interchangeable between models. A Timbre v2.5 voice (for example `Nalini`) sent with `model: "timbre-v3.0"`, or a Timbre v3.0 voice (for example `Shivani`) sent with `model: "timbre-v2.5"`, is rejected with `400 Bad Request`. The error message lists the voices the requested model supports.
</Warning>

<Tip>
  Preview voices before you integrate. Open the [Gnani TTS playground](https://app.gnani.ai/voice/text-to-speech), select a model, and use the filters to narrow by **language**, **gender**, and **persona**.
</Tip>

***

## Timbre v2.5 voices

Use these voices with `"model": "timbre-v2.5"`.

<Tip>
  Migrating from Timbre v2.0? Timbre v2.0 will be deprecated soon — move to Timbre v2.5 or Timbre v3.0 to continue receiving the latest improvements.
</Tip>

42 voices are available for Gnani Timbre v2.5. Each voice has a **preferred language** — set the `language` parameter to match for best results. Pass `auto` to detect language from the input script.

### Preferred voices by language

| Language | `language` value | Voices |
| :- | :- | :- |
| English | `en-IN` | Kaveri, Trupti, Devika, Pranav, Shlok, Girish |
| Hindi | `hi-IN` | Nalini, Bhavna, Yashvi, Urmila, Jwala, Chitra, Ambuja, Deepak, Roopesh, Vikrant, Hemraj, Jalaj, Omkar |
| Hinglish | `hi-en` | Poorvi |
| Tamil | `ta-IN` | Asmita, Trisha, Brinda, Vedika, Noopur |
| Telugu | `te-IN` | Suhana, Lehara, Lavanya, Yukti, Varuni |
| Kannada | `kn-IN` | Saanvi, Kavin |
| Malayalam | `ml-IN` | Reshma, Riyaan |
| Marathi | `mr-IN` | Zahira, Ishaan |
| Bengali | `bn-IN` | Kirra, Dhruva |
| Gujarati | `gu-IN` | Falak, Veera |
| Punjabi | `pa-IN` | Mehuli, Zayan |

<Note>
  Use each voice with its preferred `language` value. Voices listed under a language are optimized for that locale — using a mismatched `language` may reduce quality.
</Note>

### Voice library

| Voice | Gender | Recommended language | Persona | Description |
| :- | :- | :- | :- | :- |
| Ambuja | Female | Hindi | Professional | Clear, composed virtual assistant |
| Asmita | Female | Tamil | Professional | Polished, refined, smooth corporate voice |
| Bhavna | Female | Hindi | Friendly | Friendly voice for customer support |
| Brinda | Female | Tamil | Professional | Steady, even-paced professional voice |
| Chitra | Female | Hindi | Warm, empathetic | Mature voice for customer care |
| Deepak | Male | Hindi | Professional | Clear, measured voice for corporate use |
| Devika | Female | English | Professional | Authoritative voice for customer support |
| Dhruva | Male | Bengali | Conversational | Casual, relatable voice for conversations |
| Falak | Female | Gujarati | Conversational | Youthful, clear voice for narration |
| Girish | Male | English | Expressive, energetic | Warm voice with natural storytelling |
| Hemraj | Male | Hindi | Confident, authoritative | Confident voice for demos |
| Ishaan | Male | Marathi | Professional | Clear voice for instructions and narration |
| Jalaj | Male | Hindi | Expressive, energetic | Expressive voice for storytelling |
| Jwala | Female | Hindi | Friendly | Friendly, approachable everyday voice |
| Kaveri | Female | English | Professional | Firm voice for customer support |
| Kavin | Male | Kannada | Professional | Firm, articulate voice for presentations |
| Kirra | Female | Bengali | Conversational | Soft-spoken voice for casual conversations |
| Lavanya | Female | Telugu | Warm, empathetic | Soft, empathetic voice for care and support |
| Lehara | Female | Telugu | Warm, empathetic | Gentle, reassuring voice for comfort and trust |
| Mehuli | Female | Punjabi | Expressive, energetic | Expressive voice for commercials and promotions |
| Nalini | Female | Hindi | Friendly | Friendly voice for playful conversations |
| Noopur | Female | Tamil | Friendly | Warm voice for everyday conversations |
| Omkar | Male | Hindi | Confident, authoritative | Energetic voice for customer support |
| Poorvi | Female | Hinglish | Conversational | Natural voice for bilingual conversations |
| Pranav | Male | English | Friendly | Friendly voice for customer support |
| Reshma | Female | Malayalam | Friendly | Bright voice for greetings and support |
| Riyaan | Male | Malayalam | Conversational | Easygoing voice for casual conversations |
| Roopesh | Male | Hindi | Professional | Grounded, knowledgeable, professional voice |
| Saanvi | Female | Kannada | Expressive, energetic | Lively voice for ads and promotions |
| Shlok | Male | English | Conversational | Warm, conversational voice |
| Suhana | Female | Telugu | Warm, empathetic | Calm, soothing voice with confidence |
| Trisha | Female | Tamil | Friendly | Warm, approachable voice for guidance |
| Trupti | Female | English | Professional | Upbeat, articulate voice with maturity |
| Urmila | Female | Hindi | Professional | Refined voice for formal announcements |
| Varuni | Female | Telugu | Conversational | Clear, natural voice for everyday use |
| Vedika | Female | Tamil | Professional | Crisp, articulate voice for information |
| Veera | Male | Gujarati | Friendly | Friendly voice for casual conversations |
| Vikrant | Male | Hindi | Conversational | Warm, genuine conversational voice |
| Yashvi | Female | Hindi | Warm, empathetic | Gentle, reassuring voice for comfort |
| Yukti | Female | Telugu | Friendly | Warm, welcoming voice that puts listeners at ease |
| Zahira | Female | Marathi | Expressive, energetic | Energetic voice for sales and casual chat |
| Zayan | Male | Punjabi | Warm, empathetic | Soft, caring voice for empathetic conversations |

***

## Timbre v3.0 voices

Use these voices with `"model": "timbre-v3.0"`.

13 voices are available for Gnani Timbre v3.0. Unlike Timbre v2.5, **every voice speaks all 10 supported languages** — choose a voice for its gender and persona, then set `language` to the language of your text, or pass `auto` to detect it from the input script.

Supported languages: Hindi (`hi-IN`), English (`en-IN`), Tamil (`ta-IN`), Telugu (`te-IN`), Kannada (`kn-IN`), Malayalam (`ml-IN`), Marathi (`mr-IN`), Punjabi (`pa-IN`), Bengali (`bn-IN`), and Gujarati (`gu-IN`).

### Voices by gender

| Gender | Voices |
| :- | :- |
| Female | Shivani, Lakshmi, Kalpana, Chetana, Vasudha, Riyaa, Tarika |
| Male | Avinash, Shubham, Prakash, Devansh, Yashraj, Harshad |

### Voice library

| Voice | Gender | Languages | Persona | Description |
| :- | :- | :- | :- | :- |
| Avinash | Male | Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Punjabi, Bengali, Gujarati | Professional | Professional, firm voice with deliberate pacing for collections and BFSI |
| Chetana | Female | Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Punjabi, Bengali, Gujarati | Warm, empathetic | Gentle, empathetic voice for healthcare and telecom customer service |
| Devansh | Male | Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Punjabi, Bengali, Gujarati | Conversational | Energetic, young conversational voice for sales and fintech |
| Kalpana | Female | Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Punjabi, Bengali, Gujarati | Warm, empathetic | Empathetic, composed voice for customer care and insurance |
| Lakshmi | Female | Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Punjabi, Bengali, Gujarati | Expressive, energetic | Expressive, warm voice for storytelling and e-learning narration |
| Prakash | Male | Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Punjabi, Bengali, Gujarati | Professional | Steady, deliberate voice for payment recovery and BFSI |
| Riyaa | Female | Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Punjabi, Bengali, Gujarati | Confident, authoritative | Confident, lively voice for outbound sales and insurance |
| Shivani | Female | Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Punjabi, Bengali, Gujarati | Warm, empathetic | Warm, patient, empathy-first voice for inbound customer support |
| Shubham | Male | Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Punjabi, Bengali, Gujarati | Expressive, energetic | Energetic, confident voice for outbound sales and lead qualification |
| Tarika | Female | Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Punjabi, Bengali, Gujarati | Warm, empathetic | Warm, reassuring voice for banking and insurance customer care |
| Vasudha | Female | Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Punjabi, Bengali, Gujarati | Expressive, energetic | Expressive, composed voice for narration and e-learning |
| Yashraj | Male | Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Punjabi, Bengali, Gujarati | Warm, empathetic | Warm narrative voice for e-learning and IVR narration |
| Harshad | Male | Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Punjabi, Bengali, Gujarati | Professional | Professional, firm voice for collections and payment recovery |

### Audio tags

Timbre v3.0 voices can perform non-verbal cues. Place a tag inline in `text` at the point where it should happen:

`<coughs>` · `<excited>` · `<exhales>` · `<giggle>` · `<laugh>` · `<pauses>` · `<shouting>` · `<sigh>` · `<slow>` · `<sniffles>` · `<whispers>` · `<yawns>` · `<clears throat>`

See [Audio Tags](/api/TTS/tts-audio-tags) for what each tag does.

```json theme={null}
{
  "text": "Let me check that for you. <pauses> Found it <laugh> your order ships tomorrow.",
  "voice": "Shivani",
  "model": "timbre-v3.0",
  "language": "en-IN"
}
```

<Note>
  Audio tags are a Timbre v3.0 feature. With `timbre-v2.5` they are removed from the text before synthesis and are not spoken; a request whose text contains only tags is rejected with `400 Bad Request`.
</Note>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.