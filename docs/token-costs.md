# Token Costs

## How LLM pricing works

Every LLM API charges you based on **tokens** — the atomic units of text the model reads and writes. There are two separate charges:

| Metric | What it counts |
|---|---|
| **Input (prompt) tokens** | Every token the model reads — your prompt, system instructions, context, diff, repository info, everything. |
| **Output (completion) tokens** | Every token the model generates — the review body, issues, suggestions, summary. |

You are billed for **both**. The price-per-token differs between input and output (output is typically more expensive because generation costs more compute than reading).

### Token estimation in this tool

This tool uses a rough heuristic (`chars ÷ 4`) to estimate prompt tokens before the LLM call. This is used for budget enforcement (`MAX_PROMPT_TOKENS`) and for displaying pre-call estimates.

**Do not rely on it for billing.** Different models tokenize differently — GPT-4 averages ~3.7 chars/token on code, while Claude 3 averages ~3.2. Always use the API's reported `prompt_eval_count` and `eval_count` for actual billing.

### How to configure cost tracking

Set these environment variables to enable dollar-cost estimates in the review output:

```bash
# Costs per 1,000 tokens (use official pricing from each provider)
MODEL_INPUT_COST_PER_1K=0.003    # example: Claude Sonnet input
MODEL_OUTPUT_COST_PER_1K=0.015   # example: Claude Sonnet output
```

When set, `scripts/review_with_fragments.py` displays an estimated cost line after each review. The main `pr-auto-reviewer` pipeline logs token counts at INFO level regardless.

---

## Commercial model pricing

All prices in USD per 1,000,000 tokens. Prices change frequently — check the provider links for live rates.

### Anthropic (Claude)

| Model | Input / 1M tokens | Output / 1M tokens | Cached input | Notes |
|---|---|---|---|---|
| Claude Opus 4 | $15.00 | $75.00 | $3.75 | Most capable |
| Claude Sonnet 4 | $3.00 | $15.00 | $0.75 | Best price/perf |
| Claude 3.5 Haiku | $0.80 | $4.00 | $0.20 | Fast & cheap |

> **Official pricing:** https://www.anthropic.com/pricing#anthropic-api

A typical code review (~12K prompt, ~500 output) on Sonnet 4 costs: input ~$0.036 + output ~$0.008 = **~$0.044 total**.

### OpenAI (ChatGPT / GPT-4)

| Model | Input / 1M tokens | Output / 1M tokens | Cached input | Notes |
|---|---|---|---|---|
| GPT-4.1 | $2.00 | $8.00 | $0.50 | Latest flagship |
| GPT-4.1 Mini | $0.40 | $1.60 | $0.10 | Small/fast |
| GPT-4.1 Nano | $0.10 | $0.40 | $0.025 | Cheapest |
| GPT-4o | $2.50 | $10.00 | $1.25 | Default multimodal |
| GPT-4o Mini | $0.15 | $0.60 | $0.075 | Budget option |
| o3 | $10.00 | $40.00 | $2.50 | Reasoning model |
| o4-mini | $1.10 | $4.40 | $0.275 | Lightweight reasoning |

> **Official pricing:** https://openai.com/api/pricing/

Typical review on GPT-4o Mini: input ~$0.002 + output ~$0.0003 = **~$0.002 total**.

### DeepSeek

| Model | Input / 1M tokens | Output / 1M tokens | Notes |
|---|---|---|---|
| DeepSeek-V3 | $0.27 | $1.10 | General purpose |
| DeepSeek-R1 | $0.55 | $2.19 | Reasoning model |

> **Official pricing:** https://api-docs.deepseek.com/quick_start/pricing

Typical review on DeepSeek-V3: input ~$0.003 + output ~$0.001 = **~$0.004 total**.

### Google (Gemini)

| Model | Input / 1M tokens | Output / 1M tokens | Notes |
|---|---|---|---|
| Gemini 2.5 Pro | $1.25 | $10.00 | < 200K tokens |
| Gemini 2.5 Flash | $0.15 | $0.60 | Budget/fast |
| Gemini 2.0 Flash | $0.10 | $0.40 | Previous gen |

> **Official pricing:** https://ai.google.dev/pricing

---

## Local models (free)

Local models running via [Ollama](https://ollama.com) have **zero API cost**. You pay only for electricity and GPU/CPU hardware. Token tracking is still useful for understanding model capacity and prompt engineering.

Models commonly used for code review:

| Model | Approx size | Notes |
|---|---|---|
| `codellama:13b` | ~7.4 GB | Meta's code-specialised model |
| `codegemma:7b` | ~4.4 GB | Google's code model, lighter |
| `deepseek-coder-v2:16b` | ~9 GB | Strong code understanding |
| `qwen2.5-coder:14b` | ~8.5 GB | Alibaba, strong reviews |
| `llama3.2:3b` | ~2 GB | Very light, fast |
| `mistral:7b` | ~4.1 GB | General purpose, good quality |

To see exactly how many tokens you're consuming locally, set `DEBUG=1` and watch the `eval_count` (completion tokens) and prompt chars/tokens in the logs.

---

## Cost comparison per typical PR review

Assumes ~12,000 input tokens (~46K chars composed prompt) and ~500 output tokens (review + issues):

| Model | Per review | Per 100 reviews | Per 1,000 reviews |
|---|---|---|---|
| **Local (Ollama)** | $0.00 | $0.00 | $0.00 |
| GPT-4.1 Nano | $0.001 | $0.14 | $1.40 |
| GPT-4o Mini | $0.002 | $0.21 | $2.10 |
| Gemini 2.5 Flash | $0.002 | $0.21 | $2.10 |
| DeepSeek-V3 | $0.004 | $0.38 | $3.80 |
| GPT-4o | $0.035 | $3.50 | $35.00 |
| Claude Sonnet 4 | $0.044 | $4.36 | $43.60 |
| Claude Opus 4 | $0.218 | $21.75 | $217.50 |

> **Bottom line:** GPT-4o Mini, GPT-4.1 Nano, DeepSeek-V3, and Gemini Flash are all under $0.01 per review. Claude Sonnet 4 and GPT-4o are ~20-40× more per review but deliver noticeably better quality. For high-traffic repos doing 100+ reviews/day, stick with the budget tier or run local models.

---

## Reducing costs

1. **Cap prompt tokens** — set `MAX_PROMPT_TOKENS` in your `.env`. This activates `TokenBudgetManager` which greedily drops the lowest-priority fragments to stay under budget.
2. **Use compact templates** — set `USE_COMPACT_TEMPLATE=true` to strip verbose instructions from the prompt.
3. **Limit file context** — set `MAX_FILES` and `MAX_FILE_CHARS` to reduce the amount of full-file content included.
4. **Run local models** — Ollama costs nothing but electricity. A `codegemma:7b` on a consumer GPU can review PRs in seconds.
5. **Cache repository context** — prompt fragments with `priority=0` are dropped first. Keep only essential repo-specific guidance in high-priority fragments.
