> ## Documentation Index
> Fetch the complete documentation index at: https://docs.gnani.ai/llms.txt
> Use this file to discover all available pages before exploring further.

# Speech-to-Text (REST)

> Quick transcription of audio clips up to 60 seconds via HTTP.

## Overview

The REST endpoint transcribes an audio file in a single synchronous HTTP request and returns the transcript immediately. It is best suited for short, pre-recorded audio clips.

| Use case | Recommended endpoint |
| - | - |
| Short clips ≤ 60 s (ideal ≤ 30 s) | **This endpoint** |
| Live microphone / real-time audio | [STT Realtime (WebSocket)](/api/STT/stt-websocket) |
| Large files or bulk jobs | [STT Batch](/api/STTBatch/Introduction) |

***

## Endpoint

```text theme={null}
POST https://api.vachana.ai/stt/v3
Content-Type: multipart/form-data
```

***

## Authentication

Pass your API key in the request header.

| Header | Type | Required | Description |
| - | - | - | - |
| `X-API-Key-ID` | `string` | Yes | Your Gnani Prisma v2.5 API key. Obtain one from the Gnani APIs dashboard. |

***

## Request Parameters

All parameters are sent as `multipart/form-data` fields.

<ParamField body="audio_file" type="file" required>
  Audio file to transcribe. Supported formats: WAV, MP3, OGG, FLAC, AAC, M4A. Maximum duration: 60 seconds (ideal ≤ 30 s).
</ParamField>

<ParamField body="language_code" type="string" required>
  BCP-47 language code. See [Supported Languages](#supported-languages) below.
</ParamField>

<ParamField body="format" default="verbatim" type="enum">
  `verbatim` — raw spoken-form output. `transcribe` — enables Inverse Text Normalization (ITN): numbers, currency, dates, and phone numbers are written in their conventional form. See [ITN](#inverse-text-normalization-itn) below.
</ParamField>

<ParamField body="itn_native_numerals" default="false" type="boolean">
  When `format=transcribe`, set `true` to render digits in the native script of the target language (e.g. `₹५,०००` instead of `₹5,000` for Hindi). Has no effect when `format=verbatim`.
</ParamField>

<ParamField body="enable_substitution" default="false" type="boolean">
  Set to `true` to enable post-transcription find-and-replace. When enabled, all patterns listed in `substitution_map` are replaced in the final transcript text after recognition and ITN. Has no effect when `false` (default) — the `substitution_map` field is ignored entirely.
</ParamField>

<ParamField body="substitution_map" type="string">
  A JSON-encoded list of substitution rules applied to the transcript after recognition and ITN. Only evaluated when `enable_substitution=true`. Maximum **10 rules**.

  Each rule is an object with two fields:

  | Field | Type | Description |
  | - | - | - |
  | `patterns` | `string[]` | One or more strings to find. Matching is **case-insensitive** and respects Unicode word boundaries, so `"ok"` matches `"OK"` and `"Ok"` but not `"okay"`. |
  | `replacement` | `string` | The string to substitute for every matched pattern in this rule. |

  ```json theme={null}
  [
    {"patterns": ["okay", "ok", "alright"], "replacement": "acknowledged"},
    {"patterns": ["rupees", "rs"],           "replacement": "INR"}
  ]
  ```

  Rules are applied in a **single pass** — there is no risk of one replacement being re-matched by a later rule. Longer phrases take priority over shorter ones (e.g. `"New Delhi"` matches before `"Delhi"`).

  <Note>
    Substitution runs on the final client-visible transcript only. Billing records always carry the original raw transcript regardless of this setting.
  </Note>
</ParamField>

<ParamField body="bias_list" type="string">
  Words to boost during recognition — brand names, product names, or other terms the model tends to miss. Up to **100 words**, as a JSON array (`["EMI","Prisma"]`) or comma-separated (`EMI,Prisma`). Each entry must be a **single word of letters only** (no spaces, digits, punctuation, or symbols). Only takes effect together with a positive `bias_score`. See [Word Boosting](#word-boosting-bias_list) below.
</ParamField>

<ParamField body="bias_score" type="number">
  Boost strength for `bias_list`. One of `0.0`, `0.5`, `1.0`, `1.5`, `2.0`. `0.0` or omitted turns boosting off.
</ParamField>

***

## Response

### 200 — Success

```json theme={null}
{
  "success": true,
  "request_id": "req_abc123",
  "timestamp": "20251226_143052.123",
  "transcript": "नमस्ते, आप कैसे हैं?"
}
```

| Field | Type | Description |
| - | - | - |
| `success` | `boolean` | `true` when transcription completed without error. |
| `request_id` | `string` | Unique identifier for this request. Use it when contacting support or correlating logs. |
| `timestamp` | `string` | Server-side request timestamp in `YYYYMMDD_HHMMSS.mmm` format. |
| `transcript` | `string` | The transcribed text. Format depends on the `format` parameter. |

### Error Responses

| Status | Meaning |
| - | - |
| `400` | Bad request — invalid parameters or unsupported audio format. |
| `429` | Rate limit exceeded — slow down or contact support to increase limits. |
| `500` | Internal server error — transient issue on our side; retry with backoff. |
| `503` | Service unavailable — the STT service is temporarily down. |

***

## Code Example

<CodeGroup>
  ```bash cURL theme={null}
  curl --request POST \
    --url https://api.vachana.ai/stt/v3 \
    --header 'Content-Type: multipart/form-data' \
    --header 'X-API-Key-ID: <api-key>' \
    --form audio_file='@recording.wav' \
    --form language_code=hi-IN \
    --form format=transcribe \
    --form itn_native_numerals=true
  ```

  ```bash cURL (with find-and-replace) theme={null}
  curl --request POST \
    --url https://api.vachana.ai/stt/v3 \
    --header 'Content-Type: multipart/form-data' \
    --header 'X-API-Key-ID: <api-key>' \
    --form audio_file='@recording.wav' \
    --form language_code=en-IN \
    --form enable_substitution=true \
    --form 'substitution_map=[{"patterns":["okay","ok"],"replacement":"acknowledged"},{"patterns":["rupees","rs"],"replacement":"INR"}]'
  ```

  ```bash cURL (with word boosting) theme={null}
  curl --request POST \
    --url https://api.vachana.ai/stt/v3 \
    --header 'Content-Type: multipart/form-data' \
    --header 'X-API-Key-ID: <api-key>' \
    --form audio_file='@recording.wav' \
    --form language_code=hi-IN \
    --form format=verbatim \
    --form 'bias_list=["Prisma","EMI"]' \
    --form bias_score=1.0
  ```

  ```python Python SDK theme={null}
  from gnani.stt import GnaniSTTClient

  client = GnaniSTTClient(api_key="your-api-key")

  result = client.transcribe("recording.wav", language_code="hi-IN")
  print(result["transcript"])
  ```
</CodeGroup>

***

## Python SDK

The official Python SDK handles multipart construction, authentication headers, and retries automatically.

### Installation

```bash theme={null}
pip install gnani-vachana
```

Requires **Python 3.10+**.

### Authentication

The client requires an `api_key` credential. You can pass it directly or load it from environment variables.

<CodeGroup>
  ```python Constructor arguments theme={null}
  from gnani.stt import GnaniSTTClient

  client = GnaniSTTClient(
      api_key="your-api-key"
  )
  ```

  ```bash Environment variables theme={null}
  export GNANI_API_KEY="your-api-key"
  ```

  ```python Environment variables (usage) theme={null}
  from gnani.stt import GnaniSTTClient

  # Picks up credentials from environment automatically
  client = GnaniSTTClient()
  ```
</CodeGroup>

### Transcribe Audio

<CodeGroup>
  ```python From a file path theme={null}
  result = client.transcribe("recording.wav", language_code="hi-IN")
  print(result["transcript"])
  ```

  ```python From a file object theme={null}
  with open("recording.wav", "rb") as f:
      result = client.transcribe(f, language_code="hi-IN")
  print(result["transcript"])
  ```

  ```python From raw bytes theme={null}
  with open("recording.wav", "rb") as f:
      audio_bytes = f.read()

  result = client.transcribe(audio_bytes, language_code="hi-IN")
  print(result["transcript"])
  ```
</CodeGroup>

### Custom Request ID

Pass a `request_id` to correlate SDK calls with your own logs or support tickets.

```python theme={null}
result = client.transcribe(
    "call.flac",
    language_code="hi-IN",
    request_id="my-trace-123",
)
```

### Error Handling

```python theme={null}
from gnani.stt import (
    AuthenticationError,
    InvalidAudioError,
    APIError,
)

try:
    result = client.transcribe("audio.wav", language_code="hi-IN")
    print(result["transcript"])
except AuthenticationError:
    print("Invalid credentials — check your organization_id, api_key, and user_id.")
except InvalidAudioError as e:
    print(f"Bad audio file: {e}")
except APIError as e:
    print(f"API error {e.status_code}: {e}")
```

***

## Supported Languages

The Gnani Prisma v2.5 API supports 10 Indian languages.

| Language | Code | Native Script | Example |
| - | - | - | - |
| Bengali | `bn-IN` | Bengali (বাংলা) | "আমি ভাত খাই" |
| English | `en-IN` | <Tooltip tip="Accepts English-Hindi mixed audio and generates output in English (Latin script).">English (Latin)</Tooltip> | "I am going to the market" |
| Gujarati | `gu-IN` | Gujarati (ગુજરાતી) | "હું બજાર જાઉં છું" |
| Hindi | `hi-IN` | Devanagari (हिन्दी) | "मैं बाज़ार जा रहा हूँ" |
| Kannada | `kn-IN` | Kannada (ಕನ್ನಡ) | "ನಾನು ಮಾರುಕಟ್ಟೆಗೆ ಹೋಗುತ್ತೇನೆ" |
| Malayalam | `ml-IN` | Malayalam (മലയാളം) | "ഞാൻ ചന്തയിലേക്ക് പോകുന്നു" |
| Marathi | `mr-IN` | Devanagari (मराठी) | "मी बाजारात जातोय" |
| Punjabi | `pa-IN` | Gurmukhi (ਪੰਜਾਬੀ) | "ਮੈਂ ਬਾਜ਼ਾਰ ਜਾ ਰਿਹਾ ਹਾਂ" |
| Tamil | `ta-IN` | Tamil (தமிழ்) | "நான் சந்தைக்கு செல்கிறேன்" |
| Telugu | `te-IN` | Telugu (తెలుగు) | "నేను మార్కెట్‌కి వెళ్తున్నాను" |

<Note>
  **Batch STT:** Gujarati (`gu-IN`) and Punjabi (`pa-IN`) are supported here on REST but **not** on [Batch STT](/api/STTBatch/Introduction). Use REST or Realtime for those languages; use Batch for the nine languages listed on the Batch introduction page.
</Note>

***

## Inverse Text Normalization (ITN)

ITN converts the spoken-form output of the ASR engine into the conventional written form a reader expects — numbers become digits, currency gets the ₹ symbol, dates are formatted, and phone numbers are compacted — all in one pass, immediately after transcription.

**How to enable:** Set `format=transcribe` in the request body.

### What ITN Normalizes

#### 1 — Cardinal & Ordinal Numbers

Whole numbers and positional ranks are formatted using Indian comma grouping (groups of 2 after the first 3 digits).

| Spoken input (ASR) | Written output (ITN) | Rule |
| - | - | - |
| दो हज़ार | 2,000 | Indian comma grouping |
| पाँच लाख बीस हज़ार | 5,20,000 | Lakh-scale grouping |
| उन्नीस सौ चौरानवे | 1,994 | Hundred-base year form |
| five lakh | 5,00,000 | English lakh convention |
| पहला / twenty first | 1st / 21st | Ordinal suffix |

#### 2 — Currency & Money

All Indian currency expressions — including paise fractions and lakh/crore scales — are formatted with the ₹ symbol and Indian comma grouping.

| Spoken input (ASR) | Written output (ITN) | Rule |
| - | - | - |
| पाँच सौ रुपये | ₹500 | ₹ + amount |
| तीन रुपये पचास पैसे | ₹3.50 | ₹ + rupees.paise |
| दस लाख रुपये | ₹10,00,000 | ₹ + lakh grouping |
| I need five thousand rupees | ₹5,000 | English India pipeline |

#### 3 — Dates

| Spoken input (ASR) | Written output (ITN) | Rule |
| - | - | - |
| बीस जनवरी दो हज़ार पच्चीस | 20 जनवरी 2025 | DD Month YYYY (hi) |
| fifteenth january twenty twenty five | 15th January 2025 | Ordinal Month YYYY (en) |

#### 4 — Times

Indian time-of-day words (सुबह, दोपहर, शाम, रात) automatically map to 24-hour HH:MM output.

| Spoken input (ASR) | Written output (ITN) | Rule |
| - | - | - |
| सुबह पाँच बजे | सुबह 05:00 | सुबह = AM |
| शाम पाँच बजे | शाम 17:00 | शाम = evening (16–20 h) |
| रात के दस बजे | रात 22:00 | रात = night (20–24 h) |
| meeting at five fifteen in the evening | meeting 17:15 in the evening | en — 24-hour |

#### 5 — Phone Numbers & PIN Codes

Digit streams are concatenated into compact numeric strings. 10-digit streams → mobile number; 6-digit streams → PIN. Repeat prefixes (double/डबल, triple/ट्रिपल) are expanded.

| Spoken input (ASR) | Written output (ITN) | Rule |
| - | - | - |
| नौ आठ सात छह पाँच चार तीन दो एक शून्य | 9876543210 | 10 digits → phone |
| एक एक शून्य शून्य शून्य एक | 110001 | 6 digits → PIN |
| डबल आठ नौ शून्य एक दो तीन चार पाँच छह | 8890123456 | double prefix |
| one two three four five six | 123456 | English digit words |

#### 6 — Mixed & Code-Mixed Utterances

A single sentence may contain multiple entity types or blend Hindi and English. ITN handles all in one pass, normalizing each entity independently.

| Spoken input (ASR) | Written output (ITN) |
| - | - |
| कल थ्री फिफ्टी पीएम को पाँच सौ रुपये transfer करना है | कल 15:50 को ₹500 transfer करना है |

### Native Script Digits — `itn_native_numerals`

By default, ITN outputs Western Arabic digits (0–9) regardless of language. Set `itn_native_numerals=true` to render digits in the native script of the target language.

| Language | Spoken input | `false` (default) | `true` — native script |
| - | - | - | - |
| Hindi `hi-IN` | पाँच हज़ार रुपये | ₹5,000 | ₹५,००० |
| English `en-IN` | five thousand rupees | ₹5,000 | ₹5,000 (Latin — no change) |

### What ITN Does Not Change

ITN intentionally preserves idiomatic and ambiguous phrases to avoid incorrect normalization.

* **दो तीन** (meaning *a few*) stays as text, not `2` or `3`
* **कर दो / ले दो** (imperative verbs) are kept as words, not treated as cardinal 2

If a word or phrase is unchanged in the output, treat it as a failure only when the input was unambiguously a numeric entity.

***

## Find-and-Replace (Substitution)

After transcription (and after ITN, if enabled), the API can apply a custom set of find-and-replace rules to the transcript. Use this to:

* Normalise domain-specific terms ("rs" → "INR", "ok" → "acknowledged")
* Replace competitor names, internal codes, or product shortforms
* Standardise phrases that the model consistently transcribes differently from your expected output

### How to enable

Set `enable_substitution=true` and pass your rules as a JSON string in `substitution_map`.

### Rule format

```json theme={null}
[
  {"patterns": ["find1", "find2", "find3"], "replacement": "replacement1"},
  {"patterns": ["find4"],                   "replacement": "replacement2"}
]
```

* Up to **10 rules** per request.
* Each rule can list any number of `patterns` that all map to the same `replacement`.
* Matching is **case-insensitive** (`"ok"` matches `"OK"`, `"Ok"`, `"ok"`).
* Matching respects **Unicode word boundaries** — `"ok"` does not match inside `"okay"`.
* Longer phrases always match before shorter ones — `"New Delhi"` is tried before `"Delhi"`.
* Rules are applied in a **single pass** with no cascading — a replacement is never re-matched by another rule.

### Example

```bash theme={null}
curl --request POST \
  --url https://api.vachana.ai/stt/v3 \
  --header 'X-API-Key-ID: <api-key>' \
  --form audio_file='@call.wav' \
  --form language_code=en-IN \
  --form format=transcribe \
  --form enable_substitution=true \
  --form 'substitution_map=[
    {"patterns": ["okay", "ok", "alright"], "replacement": "acknowledged"},
    {"patterns": ["rupees", "rs"],           "replacement": "INR"},
    {"patterns": ["New Delhi", "Delhi"],     "replacement": "NCR office"}
  ]'
```

| Original transcript (from ASR + ITN) | After substitution |
| - | - |
| `ok, the payment of ₹500 rupees is done` | `acknowledged, the payment of ₹500 INR is done` |
| `alright, please contact the Delhi branch` | `acknowledged, please contact the NCR office branch` |

<Note>
  Substitution runs on the **final client-visible transcript only**. Billing and analytics records always carry the original raw transcript regardless of this setting.
</Note>

***

## Word Boosting (`bias_list`)

Word boosting nudges the recognizer toward specific words so they are more likely to be transcribed correctly — useful for brand names, product names, and domain terms that are otherwise misheard. It influences recognition itself; it is **not** a find-and-replace (see [Find-and-Replace](#find-and-replace-substitution) for that).

### How to use

Send both fields together:

| Field | Description |
| - | - |
| `bias_list` | Up to 100 words, as a JSON array or comma-separated string. |
| `bias_score` | `0.0`, `0.5`, `1.0`, `1.5` or `2.0`. |

| `bias_score` | Effect |
| - | - |
| `0.0` | Off (same as omitting it) |
| `0.5` | Light nudge |
| `1.0` | Typical starting point |
| `1.5` | Stronger |
| `2.0` | Maximum |

Start at `1.0` and raise only if a word is still missed — stronger boosting can make the model favour a listed word where it wasn't spoken.

### Word rules

* Each entry is **one word**. Phrases such as `"loan number"` are not allowed.
* **Letters only** — English letters or letters in the supported Indian scripts. No digits (`HDFC2`), punctuation (`HDFC-EMI`), or symbols (`@brand`).
* Casing does not matter.
* Maximum **100 words**; any beyond that are dropped.
* Use `format=verbatim`. Boost words are spoken-form tokens, so digit strings and normalized numbers won't work.
* Use a JSON array if you'd rather not worry about commas; both formats are accepted.

<Warning>
  Invalid input does **not** return an error. If any entry breaks the rules (or `bias_score` is not an allowed value), the whole list is ignored and the audio is transcribed **without** boosting, still returning `200`. If boosting seems to have no effect, check your list first.
</Warning>

### When it applies

Boosting applies when `language_code` (and every code in `multi_lang_codes`, if used) is a specific language such as `hi-IN` or `en-IN`, and you use the default model (omit `model`, or `Prisma v2.5`). It is not available on [Batch STT](/api/STTBatch/Introduction). With `multi_lang_codes`, the same list and score apply to every language.

The response format is unchanged; boosted words are not echoed back.

### Example

```bash theme={null}
curl --request POST \
  --url https://api.vachana.ai/stt/v3 \
  --header 'X-API-Key-ID: <api-key>' \
  --form audio_file='@call.wav' \
  --form language_code=en-IN \
  --form format=verbatim \
  --form bias_list=Prisma,Vachana \
  --form bias_score=1.0
```


## OpenAPI

````yaml POST /stt/v3
openapi: 3.1.0
info:
  title: Vachana Speech-to-Text API
  description: >
    Vachana STT API provides powerful speech-to-text conversion with support for
    10 Indian languages.


    ## Authentication

    All API requests require authentication using an API key passed in the
    `X-API-Key-ID` header.


    ## Supported Languages

    | Language | Code |

    |----------|------|

    | Bengali | `bn-IN` |

    | English (India) | `en-IN` |

    | Gujarati | `gu-IN` |

    | Hindi | `hi-IN` |

    | Kannada | `kn-IN` |

    | Malayalam | `ml-IN` |

    | Marathi | `mr-IN` |

    | Punjabi | `pa-IN` |

    | Tamil | `ta-IN` |

    | Telugu | `te-IN` |


    ## Audio Constraints

    - **Maximum duration**: 60 seconds (Ideal duration is 30 seconds)

    - **Supported formats**: WAV, MP3, OGG, FLAC, AAC, M4A

    - **Sample rate**: Automatically converted to 16000 Hz mono
  version: 3.0.0
servers:
  - url: https://api.vachana.ai
    description: Production Server
security:
  - ApiKeyAuth: []
paths:
  /stt/v3:
    post:
      tags:
        - Speech-to-Text
      summary: Speech to Text (REST)
      description: >
        Convert speech audio to text using Vachana's state-of-the-art
        Speech-To-Text models.


        ## Features

        - Supports 10 Indian languages with dedicated monolingual models

        - Multilingual support for English and Hindi together

        - Automatic audio format conversion


        ## Supported Languages

        | Language | Code |

        |----------|------|

        | Bengali | `bn-IN` |

        | English (India) | `en-IN` |

        | Gujarati | `gu-IN` |

        | Hindi | `hi-IN` |

        | Kannada | `kn-IN` |

        | Malayalam | `ml-IN` |

        | Marathi | `mr-IN` |

        | Punjabi | `pa-IN` |

        | Tamil | `ta-IN` |

        | Telugu | `te-IN` |


        ## Model Selection

        - **Single language**: Uses the dedicated monolingual model for that
        language

        - **Multiple languages**: Uses multilingual model (supports en-IN,
        hi-IN)


        ## Audio Constraints

        - **Maximum duration**: 30 seconds (Ideal duration is 30 seconds)

        - **Supported formats**: WAV, MP3, OGG, FLAC, AAC, M4A

        - **Sample rate**: Automatically converted to 16000 Hz mono


        ## Response

        Returns a JSON object containing:

        - `success`: Operation status (boolean)

        - `timestamp`: Request timestamp (format: YYYYMMDD_HHMMSS.mmm)

        - `transcript`: The transcribed text
      operationId: stt_decode_stt_v3_post
      requestBody:
        required: true
        content:
          multipart/form-data:
            schema:
              $ref: '#/components/schemas/Body_stt_decode_stt_v3_post'
      responses:
        '200':
          description: Successful transcription
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/STTResponse'
              example:
                success: true
                request_id: req_abc123
                timestamp: 20251226_143052.123
                transcript: नमस्ते, आप कैसे हैं?
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
                  message: >-
                    Audio duration exceeds maximum limit of 60 seconds, while
                    the ideal duration is 30 seconds.
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
                  message: Speech recognition service is temporarily unavailable.
      security:
        - ApiKeyAuth: []
components:
  schemas:
    Body_stt_decode_stt_v3_post:
      type: object
      required:
        - audio_file
        - language_code
      properties:
        audio_file:
          type: string
          format: binary
          description: >-
            Audio file to transcribe. Supported formats - WAV, MP3, OGG, FLAC,
            AAC, M4A. Maximum duration - 60 seconds (Ideal duration is 30
            seconds).
        language_code:
          type: string
          description: >
            Language code for transcription. Use one of the supported language
            codes.


            **Supported values**: `bn-IN`, `en-IN`, `gu-IN`, `hi-IN`, `kn-IN`,
            `ml-IN`, `mr-IN`, `pa-IN`, `ta-IN`, `te-IN`
          example: hi-IN
          enum:
            - bn-IN
            - en-IN
            - gu-IN
            - hi-IN
            - kn-IN
            - ml-IN
            - mr-IN
            - pa-IN
            - ta-IN
            - te-IN
        format:
          type: string
          description: >
            Output format for the transcript.


            - `verbatim` *(default)* — Returns the raw spoken-form transcript as
            recognised by the ASR engine. No post-processing is applied.

            - `transcribe` — Enables Inverse Text Normalization (ITN). Spoken
            numeric expressions, currency, dates, times, and phone numbers are
            automatically converted to their written form (e.g. "five thousand
            rupees" → "₹5,000").
          enum:
            - verbatim
            - transcribe
          default: verbatim
          example: transcribe
        itn_native_numerals:
          type: boolean
          description: >
            When `format=transcribe`, set to `true` to render digits in the
            native script of the target language instead of Western Arabic
            digits (0–9).


            For example, with `hi-IN`: "पाँच हज़ार रुपये" → `"₹५,०००"` instead
            of `"₹5,000"`.


            Has no effect when `format=verbatim`.
          default: false
          example: true
        enable_substitution:
          type: boolean
          description: >
            Set to `true` to enable post-transcription find-and-replace. All
            patterns listed in `substitution_map` are applied to the transcript
            after recognition and ITN.


            When `false` (default), the `substitution_map` field is ignored
            entirely — no performance cost.
          default: false
          example: true
        substitution_map:
          type: string
          description: >
            JSON-encoded list of substitution rules applied to the transcript
            after recognition and ITN. Only evaluated when
            `enable_substitution=true`. Maximum **10 rules**.


            Each rule must have:

            - `patterns` (array of strings) — one or more strings to find.
            Matching is case-insensitive and respects Unicode word boundaries.

            - `replacement` (string) — the string to substitute for every
            matched pattern in this rule.


            Rules are applied in a single pass — no cascading. Longer phrases
            take priority over shorter ones.


            Example value:

            ```

            [{"patterns":["okay","ok"],"replacement":"acknowledged"},{"patterns":["rupees","rs"],"replacement":"INR"}]

            ```
          example: >-
            [{"patterns":["okay","ok"],"replacement":"acknowledged"},{"patterns":["rupees","rs"],"replacement":"INR"}]
        bias_list:
          type: string
          description: >
            Words to boost during recognition (word boosting). Up to **100
            words**, sent as a JSON array or a comma-separated string. Each
            entry must be a **single word** made of letters only — no spaces,
            digits, punctuation, or symbols. Must be paired with a positive
            `bias_score`.


            Use with `format=verbatim` for best results. Applies to the
            supported languages with the default model (`Prisma v2.5`).


            An invalid list never fails the request — it is transcribed normally
            with boosting skipped.
          example: '["Timbre","Prisma","EMI"]'
        bias_score:
          type: number
          description: >
            Boost strength for `bias_list`. Allowed values: `0.0`, `0.5`, `1.0`,
            `1.5`, `2.0`. `0.0` (or omitting it) disables boosting; any other
            value is ignored and boosting is skipped.
          enum:
            - 0
            - 0.5
            - 1
            - 1.5
            - 2
          example: 1
    STTResponse:
      type: object
      properties:
        success:
          type: boolean
          description: Indicates if the transcription was successful
        timestamp:
          type: string
          description: Request timestamp in format YYYYMMDD_HHMMSS.mmm
        transcript:
          type: string
          description: The transcribed text from the audio
    StandardErrorResponse:
      type: object
      properties:
        success:
          type: boolean
          example: false
        error:
          $ref: '#/components/schemas/ErrorDetail'
    ErrorDetail:
      type: object
      properties:
        type:
          type: string
          description: A short error code string (e.g., 'INVALID_REQUEST_ERROR').
        message:
          type: string
          description: A descriptive error message.
  securitySchemes:
    ApiKeyAuth:
      type: apiKey
      in: header
      name: X-API-Key-ID
      description: API key for authentication. Sign up in Vachana to get the API Key.

````

This documentation is built and hosted on [Mintlify](https://mintlify.com), a developer documentation platform.