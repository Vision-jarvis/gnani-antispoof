> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Voice Cloned TTS (REST)

> Generate cloned voice audio in a single synchronous response.

## Overview

<Steps>
  <Step title="Step 1 — Generate a voice embedding">
    Upload a reference audio clip to get a `speaker_embedding`. See [Voice Clone Embeddings](/api/VC/voice-clone-embeddings).
  </Step>

  <Step title="Step 2 — Synthesize with your cloned voice — this page">
    Pass the `speaker_embedding` from Step 1 to this endpoint to synthesize audio in your cloned voice.
  </Step>
</Steps>

Synthesize audio using your cloned voice. Pass the `speaker_embedding` obtained from [Voice Clone Embeddings](/api/VC/voice-clone-embeddings) along with your text. The full audio is returned in one response. For streaming playback, see [Voice Cloning Streaming](/api/VC/vc-sse) or [Voice Cloning Realtime](/api/VC/vc-websocket).

## Endpoint

```
POST https://api.vachana.ai/api/v1/tts/inference
```

## Authentication

| Header | Required | Description | Example |
| - | - | - | - |
| `X-API-Key-ID` | Yes | Your API key for authentication | `your-api-key-id` |
| `Content-Type` | Yes | Must be `application/json` | `application/json` |

## Request Body

<ParamField body="text" type="string" required>
  The text to synthesize into speech
</ParamField>

<ParamField body="model" type="string">
  Voice cloning model. Use `vachana-vc-v1`. Automatically set when `speaker_embedding` is provided — you may omit this field.
</ParamField>

<ParamField body="audio_config" type="object" required>
  Audio output configuration

  <Expandable title="properties">
    <ParamField body="sample_rate" type="integer">
      Sample rate in Hz (8000-44100)
    </ParamField>

    <ParamField body="num_channels" type="integer">
      Number of audio channels (1-8)
    </ParamField>

    <ParamField body="sample_width" type="integer">
      Sample width in bytes (1-4)
    </ParamField>

    <ParamField body="encoding" type="string">
      Audio encoding format: `linear_pcm` or `oggopus`
    </ParamField>

    <ParamField body="container" type="string">
      Audio container format: `raw`, `mp3`, `wav`, `mulaw`, or `ogg`
    </ParamField>

    <ParamField body="bitrate" type="string">
      MP3 bitrate (only when container=mp3): `96k`, `128k`, or `192k`
    </ParamField>
  </Expandable>
</ParamField>

<ParamField body="speaker_embedding" type="object" required>
  Voice clone embedding obtained from the Voice Clone Embeddings endpoint

  <Expandable title="properties">
    <ParamField body="embedding" type="string" required>
      The voice clone embedding string
    </ParamField>

    <ParamField body="shape" type="array" required>
      Shape of the embedding tensor, e.g., `[1, 768]`
    </ParamField>

    <ParamField body="dtype" type="string" required>
      Data type of the embedding, e.g., `torch.bfloat16`
    </ParamField>
  </Expandable>
</ParamField>

## Response

Returns binary audio data in the format specified by `audio_config.container`:

* `audio/wav` for WAV files
* `audio/mpeg` for MP3 files
* `audio/ogg` for OGG files

## Example Request

<CodeGroup>
  ```bash cURL theme={null}
  curl -X POST https://api.vachana.ai/api/v1/tts/inference \
    -H "X-API-Key-ID: your-api-key-id" \
    -H "Content-Type: application/json" \
    -d '{
      "text": "नमस्ते, आप कैसे हैं?",
      "model": "vachana-vc-v1",
      "audio_config": {
        "sample_rate": 44100,
        "encoding": "linear_pcm",
        "container": "wav"
      },
      "speaker_embedding": {
        "embedding": "your-embedding-string",
        "shape": [1, 768],
        "dtype": "torch.bfloat16"
      }
    }' \
    --output audio.wav
  ```

  ```python Python theme={null}
  import requests

  url = "https://api.vachana.ai/api/v1/tts/inference"
  headers = {
      "X-API-Key-ID": "your-api-key-id",
      "Content-Type": "application/json"
  }
  payload = {
      "text": "नमस्ते, आप कैसे हैं?",
      "model": "vachana-vc-v1",
      "audio_config": {
          "sample_rate": 44100,
          "encoding": "linear_pcm",
          "container": "wav"
      },
      "speaker_embedding": {
          "embedding": "your-embedding-string",
          "shape": [1, 768],
          "dtype": "torch.bfloat16"
      }
  }

  response = requests.post(url, headers=headers, json=payload)

  if response.status_code == 200:
      with open("audio.wav", "wb") as f:
          f.write(response.content)
      print("Audio saved successfully")
  else:
      print(f"Error: {response.status_code}")
      print(response.json())
  ```

  ```javascript JavaScript theme={null}
  const url = "https://api.vachana.ai/api/v1/tts/inference";
  const headers = {
    "X-API-Key-ID": "your-api-key-id",
    "Content-Type": "application/json"
  };
  const payload = {
    text: "नमस्ते, आप कैसे हैं?",
    model: "vachana-vc-v1",
    audio_config: {
      sample_rate: 44100,
      encoding: "linear_pcm",
      container: "wav"
    },
    speaker_embedding: {
      embedding: "your-embedding-string",
      shape: [1, 768],
      dtype: "torch.bfloat16"
    }
  };

  fetch(url, {
    method: "POST",
    headers: headers,
    body: JSON.stringify(payload)
  })
    .then(response => response.blob())
    .then(blob => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "audio.wav";
      a.click();
    })
    .catch(error => console.error("Error:", error));
  ```
</CodeGroup>

## Error Responses

<ResponseField name="400" type="Bad Request">
  Invalid text or audio configuration

  ```json theme={null}
  {
    "success": false,
    "error": {
      "type": "INVALID_REQUEST_ERROR",
      "message": "Invalid text or audio configuration."
    }
  }
  ```
</ResponseField>

<ResponseField name="429" type="Too Many Requests">
  Rate limit exceeded

  ```json theme={null}
  {
    "success": false,
    "error": {
      "type": "RATE_LIMIT_ERROR",
      "message": "Rate limit exceeded. Please try again later."
    }
  }
  ```
</ResponseField>

<ResponseField name="500" type="Internal Server Error">
  Unexpected error occurred

  ```json theme={null}
  {
    "success": false,
    "error": {
      "type": "API_ERROR",
      "message": "An unexpected error occurred while processing."
    }
  }
  ```
</ResponseField>


## OpenAPI

````yaml VC.yml POST /api/v1/tts/inference
openapi: 3.1.0
info:
  title: Voice Cloned TTS Server
  description: >-
    Voice Cloning Text-to-Speech API — synthesize audio with a cloned voice via
    REST or SSE.
  version: 1.0.0
servers:
  - url: https://api.vachana.ai
    description: Production server
security: []
paths:
  /api/v1/tts/inference:
    post:
      summary: Voice Cloned TTS Inference
      operationId: vc_inference_api_v1_tts_inference_post
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
              $ref: '#/components/schemas/VoiceCloneRequest'
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
    VoiceCloneRequest:
      type: object
      title: VoiceCloneRequest
      description: Request body for voice cloned TTS inference.
      required:
        - text
        - speaker_embedding
        - audio_config
      properties:
        text:
          type: string
          title: Text
          description: The text to synthesize into speech.
        model:
          allOf:
            - $ref: '#/components/schemas/VCModel'
          description: >-
            Voice cloning model. Automatically set to `vachana-vc-v1` when
            `speaker_embedding` is provided.
        speaker_embedding:
          allOf:
            - $ref: '#/components/schemas/SpeakerEmbedding'
          description: Voice clone embedding from the Voice Clone Embeddings endpoint.
        audio_config:
          allOf:
            - $ref: '#/components/schemas/AudioConfig'
          description: Audio output configuration.
      example:
        text: नमस्ते, आप कैसे हैं?
        model: vachana-vc-v1
        speaker_embedding:
          embedding: <base64-encoded embedding>
          shape:
            - 1
            - 768
          dtype: torch.bfloat16
        audio_config:
          sample_rate: 44100
          num_channels: 1
          sample_width: 2
          encoding: linear_pcm
          container: wav
    StandardErrorResponse:
      type: object
      properties:
        success:
          type: boolean
          example: false
        error:
          $ref: '#/components/schemas/ErrorDetail'
    VCModel:
      type: string
      enum:
        - vachana-vc-v1
      title: VCModel
      description: Supported voice cloning model.
    SpeakerEmbedding:
      type: object
      title: SpeakerEmbedding
      description: Voice clone embedding obtained from the Voice Clone Embeddings endpoint.
      properties:
        embedding:
          type: string
          title: Embedding
          description: The base64-encoded voice clone embedding tensor.
        shape:
          type: array
          items:
            type: integer
          title: Shape
          description: Shape of the embedding tensor, e.g. [1, 768].
        dtype:
          type: string
          title: Dtype
          description: Data type of the embedding tensor, e.g. torch.bfloat16.
      required:
        - embedding
        - shape
        - dtype
    AudioConfig:
      properties:
        sample_rate:
          type: integer
          maximum: 44100
          minimum: 8000
          title: Sample Rate
          description: Sample rate in Hz
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
        - oggopus
      title: AudioEncoding
      description: Supported audio encodings.
    AudioContainer:
      type: string
      enum:
        - raw
        - mp3
        - wav
        - mulaw
        - ogg
      title: AudioContainer
      description: Supported audio containers.
    MP3Bitrate:
      type: string
      enum:
        - 96k
        - 128k
        - 192k
      title: MP3Bitrate
      description: Supported MP3 bitrate options (only used when container is mp3).

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.