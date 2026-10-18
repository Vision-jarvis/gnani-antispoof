> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Text-to-Speech (REST)

> Synchronous text-to-speech with full audio returned in one response.

## Overview

<Tip>
  **New — [Audio Tags](/api/TTS/tts-audio-tags):** Add expressive delivery on Timbre v3.0 by placing tags like `<whispers>`, `<laugh>`, or `<pauses>` inline in your text.
</Tip>

Get the complete synthesized audio in one response. Best for downloads or batch processing. For streaming playback, see [TTS Streaming](/api/TTS/tts-sse) or [TTS Realtime](/api/TTS/tts-websocket).

<Note>
  Passing numbers, IDs, dates, or currency as raw strings causes mispronunciations. See the [Input Formatting Guide](/api/TTS/tts-input-formating) for correct formatting of phone numbers, account numbers, PINs, Aadhaar, vehicle registration numbers, GSTIN, currency, and more.
</Note>

***

## Models

| Model | `model` value | Languages | Extra parameters |
| :- | :- | :- | :- |
| Timbre v3.0 | `timbre-v3.0` | 10 Indian languages (every voice speaks all 10) | `language`, `speed`, [audio tags](/api/TTS/tts-audio-tags) in `text` |
| Timbre v2.5 | `timbre-v2.5` | 10 Indian languages | `language`, `speed` |

**Supported languages:** Hindi, English, Tamil, Telugu, Kannada, Malayalam, Marathi, Punjabi, Bengali, and Gujarati.

Each model has its own voices — see the [Voice Catalog](/api/TTS/available-voices).

***

## Endpoint

```text theme={null}
POST https://api.vachana.ai/api/v1/tts/inference
```

***

## Authentication

| Header | Required | Description |
| :- | :- | :- |
| `X-API-Key-ID` | Yes | Your Gnani API key |

***

## Request Parameters

```json theme={null}
{
  "text": "नमस्ते, आप कैसे हैं?",
  "voice": "Nalini",
  "model": "timbre-v2.5",
  "language": "hi-IN",
  "speed": 1.0,
  "audio_config": {
    "sample_rate": 48000,
    "num_channels": 1,
    "sample_width": 2,
    "encoding": "linear_pcm",
    "container": "wav"
  }
}
```

<ParamField body="text" type="string" required>
  The text to synthesize into speech. Pass numbers, dates, and currency as spoken words to avoid mispronunciations — see [Input Formatting Guide](/api/TTS/tts-input-formating).
</ParamField>

<ParamField body="model" type="string" required>
  `timbre-v2.5` or `timbre-v3.0`. The model determines which voices you can use.
</ParamField>

<ParamField body="voice" type="string" required>
  Voice name from the catalog of the model you selected — voices are not shared between models.

  | `model` | Example voices | Full list |
  | :- | :- | :- |
  | `timbre-v2.5` | `Nalini`, `Kaveri`, `Deepak` | [Timbre v2.5 voices](/api/TTS/available-voices#timbre-v2-5-voices) |
  | `timbre-v3.0` | `Shivani`, `Avinash`, `Lakshmi` | [Timbre v3.0 voices](/api/TTS/available-voices#timbre-v3-0-voices) |
</ParamField>

<ParamField body="language" type="string" required>
  Language of the input text. Controls text normalization and routing.

  | Value | Language |
  | :- | :- |
  | `auto` | Auto-detect from script (recommended for mixed content) |
  | `hi-IN` | Hindi |
  | `en-IN` | English |
  | `ta-IN` | Tamil |
  | `te-IN` | Telugu |
  | `kn-IN` | Kannada |
  | `ml-IN` | Malayalam |
  | `mr-IN` | Marathi |
  | `pa-IN` | Punjabi |
  | `bn-IN` | Bengali |
  | `gu-IN` | Gujarati |
  | `hi-en` | Hinglish (code-mixed Hindi–English) |
</ParamField>

<ParamField body="speed" type="number | string" default="1.0">
  Playback speed multiplier. Numeric range: `0.85` (slowest) to `1.15` (fastest). String shortcuts: `"slow"` = 0.85, `"medium"` = 1.0, `"fast"` = 1.15.
</ParamField>

<ParamField body="audio_config" type="object">
  Controls the format of the returned audio.

  <Expandable title="audio_config fields">
    <ParamField body="audio_config.sample_rate" type="integer" default="48000">
      Sample rate in Hz. Supported: `8000`, `16000`, `22050`, `24000`, `44100`, `48000`.
    </ParamField>

    <ParamField body="audio_config.num_channels" type="integer" default="1">
      Number of audio channels. `1` for mono.
    </ParamField>

    <ParamField body="audio_config.sample_width" type="integer" default="2">
      Sample width in bytes. `2` for 16-bit audio.
    </ParamField>

    <ParamField body="audio_config.encoding" type="string" default="linear_pcm">
      Audio encoding format. Options: `linear_pcm`, `pcm_s16le`, `pcm_mulaw`, `pcm_alaw`, `oggopus`. For telephony, prefer `container=mulaw` or `container=alaw` over this field — both produce the same output. Use `oggopus` (or `container=ogg`) for a playable OGG Opus file. Not required when `container` is `mp3`.
    </ParamField>

    <ParamField body="audio_config.container" type="string" default="wav">
      Output container format. Options: `wav`, `raw`, `mp3`, `ogg`, `mulaw`, `alaw`. Use `ogg` for OGG Opus. Use `mulaw` or `alaw` for G.711 telephony (forces 8000 Hz).
    </ParamField>

    <ParamField body="audio_config.bitrate" type="string" default="128k">
      MP3 bitrate. Only used when `container` is `mp3`. Supported: `32k`, `64k`, `96k`, `128k`, `192k`.
    </ParamField>
  </Expandable>
</ParamField>

***

## Audio Format Reference

| `container` | `encoding` | Output | `sample_rate` | `bitrate` | Content-Type |
| - | - | - | - | - | - |
| `wav` | `linear_pcm` | WAV file (with header) | 8000–48000 Hz | — | `audio/wav` |
| `raw` | `linear_pcm` | Raw 16-bit PCM | 8000–48000 Hz | — | `application/octet-stream` |
| `mp3` | — | MP3 file | 8000–48000 Hz | `32k`–`192k` | `audio/mpeg` |
| `ogg` | — | OGG Opus file | 8000–48000 Hz | — | `audio/ogg` |
| `mulaw` | — | Raw G.711 µ-law | **forced 8000 Hz** | — | `audio/basic` |
| `alaw` | — | Raw G.711 A-law | **forced 8000 Hz** | — | `audio/alaw` |

**Encoding aliases** — produce identical output to the `container` rows above:

| `container` | `encoding` | Equivalent to |
| - | - | - |
| `raw` | `pcm_mulaw` | `container=mulaw` |
| `raw` | `pcm_alaw` | `container=alaw` |
| `raw` or `ogg` | `oggopus` | `container=ogg` |

`bitrate` only applies when `container=mp3`. `container=mulaw`/`alaw` override `sample_rate` to 8000 Hz.

***

## Response

A successful request returns `200 OK` with raw binary audio in the format specified by `audio_config.container`.

| Status | Meaning |
| :- | :- |
| `200` | Audio returned as binary in the requested format |
| `400` | Bad request — invalid parameters or unsupported voice |
| `429` | Rate limit exceeded |
| `500` | Internal server error — retry with backoff |
| `503` | Service temporarily unavailable |

***

## Code Example

<CodeGroup>
  ```bash cURL theme={null}
  curl -X POST https://api.vachana.ai/api/v1/tts/inference \
    -H "Content-Type: application/json" \
    -H "X-API-Key-ID: <your-api-key>" \
    -d '{
      "text": "नमस्ते, आप कैसे हैं?",
      "voice": "Nalini",
      "model": "timbre-v2.5",
      "language": "hi-IN",
      "speed": 1.0,
      "audio_config": {
        "sample_rate": 48000,
        "num_channels": 1,
        "sample_width": 2,
        "encoding": "linear_pcm",
        "container": "wav"
      }
    }' \
    --output response.wav
  ```

  ```javascript JavaScript theme={null}
  const response = await fetch("https://api.vachana.ai/api/v1/tts/inference", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-API-Key-ID": "<your-api-key>",
    },
    body: JSON.stringify({
      text: "नमस्ते, आप कैसे हैं?",
      voice: "Nalini",
      model: "timbre-v2.5",
      language: "hi-IN",
      speed: 1.0,
      audio_config: {
        sample_rate: 48000,
        num_channels: 1,
        sample_width: 2,
        encoding: "linear_pcm",
        container: "wav",
      },
    }),
  });

  const audio = await response.arrayBuffer();
  console.log("Received audio:", audio.byteLength, "bytes");
  ```

  ```python Python theme={null}
  import requests

  response = requests.post(
      "https://api.vachana.ai/api/v1/tts/inference",
      headers={
          "Content-Type": "application/json",
          "X-API-Key-ID": "<your-api-key>",
      },
      json={
          "text": "नमस्ते, आप कैसे हैं?",
          "voice": "Nalini",
          "model": "timbre-v2.5",
          "language": "hi-IN",
          "speed": 1.0,
          "audio_config": {
              "sample_rate": 48000,
              "num_channels": 1,
              "sample_width": 2,
              "encoding": "linear_pcm",
              "container": "wav",
          },
      },
  )

  with open("response.wav", "wb") as f:
      f.write(response.content)
  ```
</CodeGroup>

***

## Available Voices

Each model has its own voices, and a voice only works with its own model:

* **Timbre v2.5** — 42 voices across 10 Indian languages, English, and Hinglish, each with a preferred language. See [Timbre v2.5 voices](/api/TTS/available-voices#timbre-v2-5-voices).
* **Timbre v3.0** — 13 voices that each speak all 10 languages and support audio tags. See [Timbre v3.0 voices](/api/TTS/available-voices#timbre-v3-0-voices).

Popular examples: `Nalini` (Hindi), `Kaveri` (English), `Deepak` (Hindi), `Poorvi` (Hinglish).

***

## Python SDK

The official Python SDK handles authentication headers and binary audio responses automatically.

### Installation

```bash theme={null}
pip install gnani-vachana
```

Requires **Python 3.10+**.

### Authentication

<CodeGroup>
  ```python Constructor argument theme={null}
  from gnani.tts import GnaniTTSClient

  client = GnaniTTSClient(api_key="your-api-key")
  ```

  ```bash Environment variable theme={null}
  export GNANI_API_KEY="your-api-key"
  ```

  ```python Environment variable (usage) theme={null}
  from gnani.tts import GnaniTTSClient

  client = GnaniTTSClient()
  ```
</CodeGroup>

### Synthesize Speech

```python theme={null}
from gnani.tts import GnaniTTSClient

client = GnaniTTSClient(api_key="your-api-key")

audio = client.synthesize(
    "नमस्ते, आप कैसे हैं?",
    voice="Nalini",
    model="timbre-v2.5",
    language="hi-IN",
)

with open("output.wav", "wb") as f:
    f.write(audio)
```

### Custom Audio Config

```python theme={null}
from gnani.tts import GnaniTTSClient, AudioConfig

client = GnaniTTSClient(api_key="your-api-key")

audio = client.synthesize(
    "यह एक टेस्ट है",
    voice="Nalini",
    model="timbre-v2.5",
    language="hi-IN",
    audio_config=AudioConfig(
        sample_rate=48000,
        encoding="linear_pcm",
        container="wav",
    ),
)

with open("output.wav", "wb") as f:
    f.write(audio)
```

***


## OpenAPI

````yaml POST /api/v1/tts/inference
openapi: 3.1.0
info:
  title: TTS Server
  description: Text-to-Speech API with WebSocket, SSE and gRPC streaming support
  version: 1.0.0
servers:
  - url: https://api.vachana.ai
    description: Production server
security: []
paths:
  /api/v1/tts/inference:
    post:
      summary: TTS Inference
      operationId: tts_inference_api_v1_tts_inference_post
      parameters:
        - name: X-API-Key-ID
          in: header
          required: true
          schema:
            anyOf:
              - type: string
            title: X-Api-Key-Id
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/TextToSpeechRequest'
      responses:
        '200':
          description: Successful audio synthesis
          content:
            audio/wav:
              schema:
                type: string
                format: binary
            audio/mpeg:
              schema:
                type: string
                format: binary
            audio/ogg:
              schema:
                type: string
                format: binary
        '400':
          description: Bad Request
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/StandardErrorResponse'
              example:
                success: false
                error:
                  type: INVALID_REQUEST_ERROR
                  message: Invalid text or audio configuration.
        '403':
          description: Forbidden
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/StandardErrorResponse'
              example:
                success: false
                error:
                  type: FORBIDDEN
                  message: >-
                    You do not have permission to access this resource. Check
                    your API key, organization status, or available credits.
        '429':
          description: Too Many Requests
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/StandardErrorResponse'
              example:
                success: false
                error:
                  type: RATE_LIMIT_ERROR
                  message: Rate limit exceeded. Please try again later.
        '500':
          description: Internal Server Error
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/StandardErrorResponse'
              example:
                success: false
                error:
                  type: API_ERROR
                  message: An unexpected error occurred while processing.
        '503':
          description: Service Unavailable
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/StandardErrorResponse'
              example:
                success: false
                error:
                  type: SERVICE_UNAVAILABLE
                  message: Text-to-speech service is temporarily unavailable.
components:
  schemas:
    TextToSpeechRequest:
      properties:
        text:
          type: string
          title: Text
          description: >-
            Text to synthesize. With `timbre-v3.0` the text may carry inline
            audio tags: `<coughs>`, `<excited>`, `<exhales>`, `<giggle>`,
            `<laugh>`, `<pauses>`, `<shouting>`, `<sigh>`, `<slow>`,
            `<sniffles>`, `<whispers>`, `<yawns>`, `<clears throat>` — for
            example `Let me check. <pauses> Found it <laugh>`. With
            `timbre-v2.5` these tags are removed before synthesis and are not
            spoken; text consisting only of tags is rejected with 400.
        voice:
          type: string
          title: Voice
          description: >-
            Voice name from the catalog of the requested model. `timbre-v3.0`
            voices: Avinash, Shivani, Lakshmi, Kalpana, Shubham, Prakash,
            Devansh, Yashraj, Chetana, Vasudha, Riyaa, Tarika and Harshad (each
            speaks all supported languages).
        model:
          allOf:
            - $ref: '#/components/schemas/TTSModel'
        language:
          type: string
          title: Language
          description: >-
            Language code. Use `auto`, `hi-IN`, `en-IN`, `hi-en`, `ta-IN`,
            `te-IN`, `kn-IN`, `ml-IN`, `mr-IN`, `pa-IN`, `bn-IN`, or `gu-IN`.
        speed:
          type: number
          title: Speed
          description: 'Playback speed multiplier. Range: 0.85–1.15.'
        audio_config:
          allOf:
            - $ref: '#/components/schemas/AudioConfig'
      type: object
      required:
        - text
        - model
        - audio_config
      title: TextToSpeechRequest
      description: Request body for TTS inference.
      example:
        text: नमस्ते, आप कैसे हैं?
        voice: Nalini
        model: timbre-v2.5
        language: hi-IN
        speed: 1
        audio_config:
          encoding: linear_pcm
          container: wav
          num_channels: 1
          sample_rate: 48000
          sample_width: 2
    StandardErrorResponse:
      type: object
      properties:
        success:
          type: boolean
          example: false
        error:
          $ref: '#/components/schemas/ErrorDetail'
    TTSModel:
      type: string
      enum:
        - timbre-v2.5
        - timbre-v3.0
      title: TTSModel
      description: >-
        TTS model: `timbre-v2.5` or `timbre-v3.0`. Each model has its own voice
        catalog, and a voice from one cannot be used with the other.
        `timbre-v3.0` additionally supports inline audio tags in `text`.
    AudioConfig:
      properties:
        sample_rate:
          type: integer
          maximum: 48000
          minimum: 8000
          title: Sample Rate
          description: >-
            Sample rate in Hz. Supported: 8000, 16000, 22050, 24000, 44100,
            48000
        num_channels:
          type: integer
          maximum: 8
          minimum: 1
          title: Num Channels
          description: Number of audio channels
        sample_width:
          type: integer
          maximum: 4
          minimum: 1
          title: Sample Width
          description: Sample width in bytes
        encoding:
          allOf:
            - $ref: '#/components/schemas/AudioEncoding'
          description: Audio encoding format
        container:
          allOf:
            - $ref: '#/components/schemas/AudioContainer'
          description: Audio container format
        bitrate:
          allOf:
            - $ref: '#/components/schemas/MP3Bitrate'
          description: MP3 bitrate (only used when container=mp3)
      type: object
      title: AudioConfig
      description: Audio output configuration.
    ErrorDetail:
      type: object
      properties:
        type:
          type: string
          description: A short error code string (e.g., 'INVALID_REQUEST_ERROR').
        message:
          type: string
          description: A descriptive error message.
    AudioEncoding:
      type: string
      enum:
        - linear_pcm
        - pcm_s16le
        - pcm_mulaw
        - pcm_alaw
        - oggopus
      title: AudioEncoding
      description: >-
        Supported audio encodings. Use pcm_mulaw or pcm_alaw for G.711 telephony
        codecs (forces 8000 Hz output). Use oggopus or set container=ogg to
        receive a playable OGG Opus file.
    AudioContainer:
      type: string
      enum:
        - raw
        - mp3
        - wav
        - mulaw
        - alaw
        - ogg
      title: AudioContainer
      description: Supported audio containers.
    MP3Bitrate:
      type: string
      enum:
        - 32k
        - 64k
        - 96k
        - 128k
        - 192k
      title: MP3Bitrate
      description: >-
        Supported MP3 bitrate options (only used when container is MP3).
        Default: 128k

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.