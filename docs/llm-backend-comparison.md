# LLM Backend Prompt Comparison

## Shared foundation

Both backends build the **same prompt text** via `BaseLlmAdapter`. The composed
string is split on the separator `"\n\n---\n\n"` — everything before the first
separator becomes the **system prompt**, everything after becomes the **user
prompt**.

```
SYSTEM PROMPT ("You are a Senior Principal Software Engineer...")
\n\n---\n\n
USER PROMPT (architecture context + diff + "REMEMBER: Output ONLY a raw JSON object...")
```

## How they differ

|                    | llama.cpp                                          | Ollama                                       |
|--------------------|----------------------------------------------------|----------------------------------------------|
| Endpoint           | `POST {host}/v1/chat/completions`                  | `POST {host}/api/generate`                   |
| API style          | OpenAI-compatible chat                             | Ollama-native completion                     |
| System prompt      | `messages[0] = {"role": "system", "content": …}`   | top-level `"system"` field                   |
| User prompt        | `messages[1] = {"role": "user", "content": …}`     | top-level `"prompt"` field                   |
| Model              | omitted (server serves one model)                  | required (`"model": "qwen3:14b"`)            |
| `temperature`      | `0.2`                                              | **not sent** (uses server default)           |
| `max_tokens`       | `9999`                                             | **not sent** (uses server default)           |

## Request examples

### llama.cpp

```http
POST /v1/chat/completions HTTP/1.1
Content-Type: application/json

{
  "messages": [
    {
      "role": "system",
      "content": "You are a Senior Principal Software Engineer and Code Reviewer…\n\n## CRITICAL: UNDERSTANDING UNIFIED DIFF FORMAT…"
    },
    {
      "role": "user",
      "content": "\n\n## Architecture / Context\n\nLayered architecture\n\n## Project conventions\n\nUse type hints\n\n## Repository Structure\n\nsrc/\n  main.py\n  utils/\n\n\n---\n\n## Diff\n\n```diff\ndiff --git a/…"
    }
  ],
  "temperature": 0.2,
  "max_tokens": 9999,
  "stream": false
}
```

**Response:**
```json
{
  "choices": [
    {
      "message": {
        "content": "{\"verdict\": \"approved\", \"summary\": \"…\", \"items\": [], …}"
      }
    }
  ],
  "usage": {
    "completion_tokens": 342
  },
  "timings": {
    "predicted_ms": 4521
  }
}
```

### Ollama

```http
POST /api/generate HTTP/1.1
Content-Type: application/json

{
  "model": "qwen3:14b",
  "system": "You are a Senior Principal Software Engineer and Code Reviewer…\n\n## CRITICAL: UNDERSTANDING UNIFIED DIFF FORMAT…",
  "prompt": "\n\n## Architecture / Context\n\nLayered architecture\n\n## Project conventions\n\nUse type hints\n\n## Repository Structure\n\nsrc/\n  main.py\n  utils/\n\n\n---\n\n## Diff\n\n```diff\ndiff --git a/…",
  "stream": false
}
```

**Response:**
```json
{
  "model": "qwen3:14b",
  "response": "{\"verdict\": \"changes_requested\", \"summary\": \"…\", \"items\": […], …}",
  "eval_count": 512,
  "eval_duration": 5420000000
}
```

## Key semantic difference

The `messages` array in the chat-completions API explicitly models **role** — the
model knows which part is instruction (system) and which is data (user). The
Ollama native `prompt` + `system` format treats them as separate flat fields,
which can lead to different model behavior even with identical text:

- **Chat format** (`messages`): Most models are fine-tuned on this structure.
  Instructions in the system role are treated as persistent constraints.
- **Completion format** (`prompt` + `system`): The system prompt overrides
  the model's baked-in Modelfile system prompt, but the distinction between
  "instructions" and "content to review" is less structured.

This is the most likely reason different models produce different verdicts on
the same PR — the prompt text is identical, but the structural framing affects
how the model interprets it.
