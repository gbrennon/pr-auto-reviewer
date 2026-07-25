# Fix Report: TERMINAL_OUTPUT + HTTP Request Audit

**Date:** 2026-07-25

---

## Issue 1: `TERMINAL_OUTPUT=terminal` Has No Effect

### Symptom
Running `make review TERMINAL_OUTPUT=terminal` still posts the review to the Git platform
instead of printing to stdout.

### Root Cause
The Makefile `review` and `review-force` targets only forwarded `$(REVIEW_OUTPUT)`.
The environment variable controlling output mode is `REVIEW_OUTPUT`, not `TERMINAL_OUTPUT`.
Passing `TERMINAL_OUTPUT=terminal` on the command line had no effect because Make never
forwarded it to the Python process.

The Python side was already correct:

| Component | Status |
|---|---|
| `ConfigBuilder` (lines 122-128) | Maps `REVIEW_OUTPUT=terminal` → `output_mode="terminal"` correctly |
| `_container.py:_wire()` (line 77) | Checks `config.output_mode == "terminal"` and skips platform publisher |
| `_platform_adapters.py` | Wires `TerminalReviewPublisherAdapter` when `is_terminal=True` |
| `TerminalReviewPublisherAdapter` | Outputs review to stdout only — no HTTP calls |

### Fix
**File:** `Makefile`, lines 66 and 69

```makefile
# Before
@env REVIEW_OUTPUT="$(REVIEW_OUTPUT)" uv run python -m pr_auto_reviewer review ...

# After
@env REVIEW_OUTPUT="$(or $(TERMINAL_OUTPUT),$(REVIEW_OUTPUT))" uv run python -m pr_auto_reviewer review ...
```

GNU Make's `$(or ...)` resolves the first non-empty value. `TERMINAL_OUTPUT` takes priority.
When neither is set, empty string passes through and `ConfigBuilder` defaults to `"forgejo"`.

### Verification

| Test | Result |
|---|---|
| `make review-force --dry-run TERMINAL_OUTPUT=terminal` | `REVIEW_OUTPUT="terminal"` forwarded correctly |
| `make review-force --dry-run` (no env vars) | `REVIEW_OUTPUT=""` falls back to default |
| Full test suite (1468 tests) | 0 failures, no regressions |

---

## Issue 2: 13 HTTP Requests for a Single PR Review

### Finding
**Not a bug.** The request count matches the number of API calls necessary for a PR with
7 changed files.

### Breakdown (PR #292, 7 files)

| # | Endpoint | Purpose |
|---|---|---|
| 1 | `GET /pulls/{N}` | PR metadata |
| 1 | `GET /pulls/{N}.diff` | Raw diff |
| 7 | `GET /contents/{file}?ref=` | File contents (one per changed file) |
| 1 | `GET /pulls/{N}/commits` | Commit messages |
| 1 | `GET /git/trees/{sha}?recursive=1` | Repository tree listing |
| 1 | `GET /pulls/{N}/reviews` | Existing reviews (dedup check) |
| 1 | `POST /pulls/{N}/reviews` | Publish review |
| **13** | **Total** | |

### Why This Is Expected

- No batch file-content endpoint exists on GitHub or Forgejo — each file must be fetched
  individually (see `AGENTS.md` §3.4).
- Sequential fetch is intentional: parallel requests would exhaust rate limits before
  `RateLimitTracker` can back off.
- All requests pass through `HttpRequestCounter` in `GitPlatformHttpClient`
  (`get`, `get_raw`, `post` all call `_request` → `_log_response_detail` → `record`).

---

## Scope of Changes

1 file changed:
- `Makefile` — 2 lines (both `review` and `review-force` targets)

No Python source changes. No tests changed.
