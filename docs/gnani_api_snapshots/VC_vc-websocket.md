> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Voice Cloned TTS (Realtime)

> Real-time cloned voice audio streaming via WebSocket.

## Overview

<Steps>
  <Step title="Step 1 — Generate a voice embedding">
    Upload a reference audio clip to get a `speaker_embedding`. See [Voice Clone Embeddings](/api/VC/voice-clone-embeddings).
  </Step>

  <Step title="Step 2 — Synthesize with your cloned voice — this page">
    Pass the `speaker_embedding` from Step 1 to this endpoint to stream cloned voice audio in real-time with the lowest latency.
  </Step>
</Steps>

Stream cloned voice audio in real-time with the lowest latency via WebSocket. Pass the `speaker_embedding` from [Voice Clone Embeddings](/api/VC/voice-clone-embeddings) to use your cloned voice. For simpler use cases, see [Voice Cloning REST](/api/VC/vc-inference) or [Voice Cloning Streaming](/api/VC/vc-sse).

## Endpoint

```
wss://api.vachana.ai/api/v1/tts
```

## Authentication

All Realtime connections require the following headers:

| Header | Required | Description | Example |
| - | - | - | - |
| `Content-Type` | Yes | Must be `application/json` | `application/json` |
| `X-API-Key-ID` | Yes | Your API key for authentication | `<your-api-key-id>` |

## Request Format

Send a JSON message with the following structure:

```json theme={null}
{
  "text": "नमस्ते, आप कैसे हैं?",
  "model": "vachana-vc-v1",
  "audio_config": {
    "sample_rate": 44100,
    "encoding": "linear_pcm"
  },
  "speaker_embedding": {
    "embedding": "<your-embedding-string>",
    "shape": [1, 768],
    "dtype": "torch.bfloat16"
  }
}
```

## Response

The server uses the same WebSocket message protocol as [TTS Realtime](/api/TTS/tts-websocket). Send a JSON synthesis request; receive JSON-wrapped base64 audio chunks.

### Connection flow

1. Connect to `wss://api.vachana.ai/api/v1/tts` with `X-API-Key-ID`.
2. Send a JSON message with `text`, `model`, `speaker_embedding`, and `audio_config`.
3. Receive `start`, then `audio` chunks, then `complete`.
4. Decode each chunk's `data.audio` from base64 and append in order.

### Server messages

**`start`** — synthesis began:

```json theme={null}
{ "type": "start", "message": "Streaming started", "request_id": "req_abc123" }
```

**Audio chunk:**

```json theme={null}
{
  "type": "audio",
  "data": {
    "chunk_index": 1,
    "audio": "<base64-encoded audio bytes>",
    "is_final": false
  }
}
```

**`complete`** — all audio sent:

```json theme={null}
{
  "type": "complete",
  "data": {
    "chunk_index": 12,
    "audio": "",
    "is_final": true
  }
}
```

**`error`** — synthesis failed:

```json theme={null}
{
  "type": "error",
  "error": "SYNTHESIS_FAILED",
  "message": "Human-readable error description"
}
```

<Note>
  Include a complete `audio_config` (`sample_rate`, `num_channels`, `sample_width`, `encoding`, `container`) matching [VC REST](/api/VC/vc-inference) examples.
</Note>

## Example Usage

<CodeGroup>
  ```javascript JavaScript theme={null}
  const ws = new WebSocket("wss://api.vachana.ai/api/v1/tts", {
    headers: {
      "Content-Type": "application/json",
      "X-API-Key-ID": "<your-api-key>",
    },
  });

  ws.on("open", () => {
    const request = {
      text: "नमस्ते, आप कैसे हैं?",
      model: "vachana-vc-v1",
      audio_config: {
        sample_rate: 44100,
        encoding: "linear_pcm",
      },
      speaker_embedding: {
        embedding: "<your-embedding-string>",
        shape: [1, 768],
        dtype: "torch.bfloat16",
      },
    };

    ws.send(JSON.stringify(request));
  });

  ws.on("message", (data) => {
    // Handle audio chunks
    console.log("Received audio chunk:", data);
  });

  ws.on("error", (error) => {
    console.error("WebSocket error:", error);
  });

  ws.on("close", () => {
    console.log("WebSocket connection closed");
  });
  ```

  ```python Python theme={null}
  import websocket
  import json

  def on_message(ws, message):
      # Handle audio chunks
      print(f"Received audio chunk: {len(message)} bytes")

  def on_error(ws, error):
      print(f"Error: {error}")

  def on_close(ws, close_status_code, close_msg):
      print("WebSocket connection closed")

  def on_open(ws):
      request = {
          "text": "नमस्ते, आप कैसे हैं?",
          "model": "vachana-vc-v1",
          "audio_config": {
              "sample_rate": 44100,
              "encoding": "linear_pcm"
          },
          "speaker_embedding": {
              "embedding": "<your-embedding-string>",
              "shape": [1, 768],
              "dtype": "torch.bfloat16"
          }
      }
      ws.send(json.dumps(request))

  ws = websocket.WebSocketApp(
      "wss://api.vachana.ai/api/v1/tts",
      header={
          "Content-Type": "application/json",
          "X-API-Key-ID": "<your-api-key>"
      },
      on_open=on_open,
      on_message=on_message,
      on_error=on_error,
      on_close=on_close
  )

  ws.run_forever()
  ```
</CodeGroup>


This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.