> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Voice Clone Embeddings

> Generate voice clone embeddings from an audio file.

## Voice Cloning Flow

Voice cloning is a two-step process. Complete Step 1 once per voice, then reuse the embedding across any synthesis endpoint.

<Steps>
  <Step title="Generate a voice embedding — this page">
    Upload 5–30 seconds of clean reference audio to extract a `speaker_embedding`. Cache the result — you only need to generate it once per voice.
  </Step>

  <Step title="Synthesize with your cloned voice">
    Pass the `speaker_embedding` from Step 1 to your preferred synthesis endpoint:

    <CardGroup cols={3}>
      <Card title="REST" icon="bolt" href="/api/VC/vc-inference">
        Full audio returned in a single response
      </Card>

      <Card title="Streaming (SSE)" icon="bars-staggered" href="/api/VC/vc-sse">
        Receive audio progressively as it's synthesized
      </Card>

      <Card title="Realtime (WebSocket)" icon="wave-sine" href="/api/VC/vc-websocket">
        Lowest latency — stream text in, audio out
      </Card>
    </CardGroup>
  </Step>
</Steps>

***

## Overview

Generate a `speaker_embedding` from a reference audio clip. Upload the file and receive a multi-dimensional embedding you can pass to any Voice Cloned TTS endpoint.


## OpenAPI

````yaml POST /api/v1/tts/voice-clone/embeddings
openapi: 3.1.0
info:
  title: Voice Cloning API
  version: 1.0.0
  description: >-
    API for generating voice clone embeddings and synthesizing audio with a
    cloned voice.
servers:
  - url: https://api.vachana.ai
security: []
paths:
  /api/v1/tts/voice-clone/embeddings:
    post:
      tags:
        - Voice Clone
      summary: Voice Clone Embeddings
      description: Generate voice clone embeddings from a provided audio file.
      operationId: voice_clone_embeddings
      parameters:
        - name: X-API-Key-ID
          in: header
          required: true
          schema:
            type: string
          description: API Key ID for authentication
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              type: object
              required:
                - audio_file
              properties:
                audio_file:
                  type: string
                  format: binary
                  description: The audio file to generate embeddings for
      responses:
        '200':
          description: Voice embeddings generated successfully
          content:
            application/json:
              schema:
                type: object
                properties:
                  success:
                    type: boolean
                    example: true
                  message:
                    type: string
                    example: Voice embeddings generated successfully
                  data:
                    type: object
                    properties:
                      voice_clone_embedding:
                        type: object
                        properties:
                          embedding:
                            type: string
                            description: The generated voice clone embedding string
                          shape:
                            type: array
                            items:
                              type: integer
                            example:
                              - 1
                              - 768
                            description: The shape of the embedding tensor
                          dtype:
                            type: string
                            example: torch.bfloat16
                            description: The data type of the embedding

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.