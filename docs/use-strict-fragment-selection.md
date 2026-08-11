# USE_STRICT_FRAGMENT_SELECTION — Behavior & Tuning Guide

## Overview

`USE_STRICT_FRAGMENT_SELECTION` controls how the `ComposeReviewPromptAdapter` selects which review-guideline fragments to include in the LLM prompt. It is a boolean feature flag read from the environment:

```bash
USE_STRICT_FRAGMENT_SELECTION=true   # strict mode
USE_STRICT_FRAGMENT_SELECTION=false  # default — include all fragments
```

## How fragment selection works

The adapter always loads two groups of fragments:

1. **Language-specific fragments** — from `content/<language>/` (e.g., `content/python/error-handling.md`)
2. **Universal fragments** — from `content/universal/` (e.g., `content/universal/solid-principles.md`)

What happens next depends on the flag.

---

## Mode: `false` (default)

**All fragments are included.** Language-specific and universal fragments are merged, sorted by priority (highest first), and passed through the token budget manager if one is configured.

```
Language fragments (5) + Universal fragments (5) → 10 fragments → sorted by priority → prompt
```

**When to use**: General-purpose reviews where you want comprehensive coverage. The LLM sees all guidelines and decides which are relevant. Works well when your token budget is generous.

**Tradeoff**: Larger prompts. With many fragments, the prompt can grow significantly, increasing latency and cost.

---

## Mode: `true` (strict)

**Fragments are filtered by relevance to the PR.** Only fragments whose content or metadata relates to the actual diff and file paths are included. The filtering uses a three-tier heuristic:

### Tier 1 — Always included

Fragments with `category: system` in their YAML front matter, or with `priority >= 900`, are **always** included regardless of content match. These are your non-negotiable guidelines (e.g., the reviewer system prompt).

```yaml
---
id: reviewer-system-prompt
category: system
priority: 1000
---
```

### Tier 2 — Explicit metadata match

Fragment authors can declare relevance via YAML front matter:

- **`keywords`** — comma-separated terms. If any keyword appears in the diff text or file paths, the fragment is included.
- **`match_files`** or **`match_paths`** — comma-separated path patterns. If any pattern is a substring of any changed file path, the fragment is included.

```yaml
---
id: error-handling
keywords: exception, try, catch, error, raise, throw, panic
match_files: src/, lib/, pkg/
---
```

### Tier 3 — Content heuristic (fallback)

For fragments without explicit metadata, the adapter extracts up to 15 distinct words (≥4 characters) from the fragment body and checks if any appear in the diff text or file paths. This is a lightweight keyword-overlap heuristic — not semantic analysis.

### Fallback: empty selection

If strict filtering eliminates **all** fragments (including language-specific ones), the adapter falls back to including everything — the same behavior as `false`. This prevents sending an empty prompt to the LLM.

```
Language fragments (5) → filter → 2 match
Universal fragments (5) → filter → 1 match (system) + 1 match (keyword)
Total: 4 fragments → sorted by priority → prompt
```

**When to use**: Targeted reviews where you want the LLM to focus only on guidelines relevant to the actual changes. Reduces prompt size, latency, and cost. Particularly effective for small, focused PRs.

**Tradeoff**: A fragment might be relevant but not match the heuristic (e.g., a guideline about "naming conventions" when the diff only contains new variable names that don't include the word "naming"). The fallback prevents total exclusion, but individual fragments can still be missed.

---

## Tuning fragment metadata for strict mode

To get the best results with `USE_STRICT_FRAGMENT_SELECTION=true`, add metadata to your fragment `.md` files:

### Recommended: add `keywords` to every fragment

```yaml
---
id: concurrency
language: go
priority: 80
category: correctness
keywords: goroutine, channel, mutex, waitgroup, sync, concurrent, race, select, context
---
```

Choose keywords that would appear in a diff touching the relevant code. Think about function names, package imports, error messages, and type names.

### Optional: add `match_files` for path-based fragments

```yaml
---
id: testing-practices
language: universal
priority: 70
match_files: _test, test_, spec_, __tests__
---
```

### Priority tuning

Set `priority` to control ordering when multiple fragments match:

- `1000+` — system-level, always included (reviewer persona, output format)
- `100–999` — language-specific best practices
- `1–99` — supplementary guidelines
- `0` — informational only

---

## Comparison: both modes on the same PR

| Aspect | `false` (all fragments) | `true` (strict) |
|---|---|---|
| Prompt size | ~8–15 fragments | ~3–7 fragments |
| Coverage | Comprehensive | Targeted |
| Latency | Higher | Lower |
| Risk of missing relevant guideline | None | Low (heuristic gaps) |
| Best for | Broad reviews, large PRs | Focused reviews, small PRs, cost-sensitive |

Both modes produce good reviews. The choice is a tradeoff between comprehensiveness and efficiency. The strict mode's heuristic is conservative — it errs on the side of inclusion (system fragments always pass, empty results fall back to all).

---

## Implementation reference

- **Flag parsing**: `src/pr_auto_reviewer/infrastructure/config/config.py` — `use_strict_fragment_selection` field
- **Selection logic**: `src/pr_auto_reviewer/infrastructure/fragments/compose_review_prompt_adapter.py` — `_select_fragments()` method (line 83)
- **Fragment metadata**: YAML front matter in `fragments/content/**/*.md` (repo root)