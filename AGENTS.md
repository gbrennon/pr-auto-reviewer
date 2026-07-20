# AI Guardrails — What Must Not Change

This document defines the **immutable boundaries** of this codebase for AI
agents. Nothing here should change unless official upstream documentation
proves the assumption is now wrong.

For architecture *flow* and *design rationale*, see
`docs/review-flow-architecture.md`. For verdict-to-event mapping details,
see `docs/verdict-event-mapping.md`.

---

## 1. Architecture Invariants

### 1.1 Hexagonal Boundaries

```
Domain ──── Application ──── Infrastructure ──── Presentation
  |              |                |                    |
  entities    use cases       HTTP/LLM/FS            CLI/daemon
  value objs  ports           adapters               DI wiring
```

| Rule | Location to check |
|---|---|
| Domain + Application have **zero** imports from Infrastructure or Presentation | `grep -r "infrastructure\|presentation" src/pr_auto_reviewer/domain src/pr_auto_reviewer/application` |
| All I/O goes through `Protocol`-based ports in `application/ports/` | `src/pr_auto_reviewer/application/ports/` |
| Infrastructure *implements* ports; never defines new public interfaces Application depends on | All files in `src/pr_auto_reviewer/infrastructure/` |
| DI wiring happens **only** in `presentation/composition_root.py` | `src/pr_auto_reviewer/presentation/composition_root.py` |

### 1.2 Frozen Domain Objects

All domain value objects are `frozen=True` dataclasses. "Mutation" means
`dataclasses.replace()`, never attribute assignment.

```
src/pr_auto_reviewer/domain/value_objects/code_review.py   # CodeReview
src/pr_auto_reviewer/domain/value_objects/review_verdict.py # ReviewVerdict
src/pr_auto_reviewer/domain/value_objects/review_item.py    # ReviewItem
src/pr_auto_reviewer/domain/value_objects/item_severity.py  # ItemSeverity
```

**DO NOT** unfreeze these. **DO NOT** add mutable fields or side-effectful
`__post_init__`.

### 1.3 Port Signatures

All outbound ports are `Protocol` classes. Their method signatures are the
contract between Application and Infrastructure.

```
src/pr_auto_reviewer/application/ports/outbound/
├── changeset_fetcher_port.py
├── fragment_repository_port.py
├── llm_review_port.py
├── preflight_filter_port.py
├── prompt_renderer_port.py
├── repository_context_port.py
├── review_context_factory_port.py
├── review_publisher_port.py
├── review_repository_port.py
└── token_verifier_port.py
```

**DO NOT** change method names, parameter counts, or return types without
updating every adapter that implements the port.

---

## 2. External API Contracts

### 2.1 Forgejo/Codeberg REST API

**Reference:** <https://forgejo.org/docs/latest/user/api-usage/>

| Endpoint | Method | Adapter / File |
|---|---|---|
| `/repos/{owner}/{repo}/pulls/{number}.diff` | GET (raw) | `ForgejoChangesetFetcher.fetch()` — `infrastructure/forgejo/changeset_fetcher.py` |
| `/repos/{owner}/{repo}/pulls/{number}/commits` | GET | `ForgejoChangesetFetcher._fetch_commit_messages()` |
| `/repos/{owner}/{repo}/raw/{sha}/{file_path}` | GET (raw) | `ForgejoChangesetFetcher.fetch()` |
| `/repos/{owner}/{repo}/pulls/{number}/reviews` | POST | `ReviewPublishingService.publish_formal_review()` — `infrastructure/review_publishers/review_publishing_service.py` |
| `/repos/{owner}/{repo}/issues/{number}/comments` | POST | `ReviewPublishingService.publish_comment()` |
| `/repos/{owner}/{repo}/pulls/{number}/reviews` | GET | `ReviewPublishingService.count_existing_items()` |

**Headers:** `Authorization: token <TOKEN>`; rate limits: `x-ratelimit-limit`, `x-ratelimit-remaining`, `x-ratelimit-reset`.

**Forgejo quirks (DO NOT "fix" — these match the actual API):**

| Quirk | Where |
|---|---|
| Verdict event `APPROVE` is sent as `"APPROVED"` (Forgejo rejects `"APPROVE"`) | `ForgejoReviewPublisher.publish()` — `infrastructure/review_publishers/forgejo_review_publisher.py` |
| Inline comments are embedded in the `POST /reviews` body, not posted separately | `ReviewPublishingService.publish_formal_review()` lines 87-153 |
| `official=True` is set on the review payload | Same file; GitHub version omits this |

### 2.2 GitHub REST API

**Reference:** <https://docs.github.com/en/rest>

| Endpoint | Method | Adapter / File | GitHub-specific |
|---|---|---|---|
| `/repos/{owner}/{repo}/pulls/{number}.diff` | GET (raw) | `GithubChangesetFetcher.fetch()` — `infrastructure/github/changeset_fetcher.py` | `Accept: application/vnd.github.diff` header is **mandatory** — GitHub returns `application/octet-stream` without it |
| `/repos/{owner}/{repo}/contents/{file_path}?ref={sha}` | GET | Same file | Base64-encoded content in `{content: ...}` |

**GitHub quirks (DO NOT "fix"):**

| Quirk | Where |
|---|---|
| No `official` field on review payload — field doesn't exist in GitHub API | `GithubReviewPublisher` omits it |
| File content fetched from `/contents/` (base64), not `/raw/` (Forgejo path) | `GithubChangesetFetcher.fetch()` |
| Diff endpoint needs `Accept: application/vnd.github.diff` | `GithubChangesetFetcher.fetch()` |

### 2.3 Ollama LLM API

**Reference:** <https://github.com/ollama/ollama/blob/main/docs/api.md>

**Adapter:** `src/pr_auto_reviewer/infrastructure/llm/ollama_llm_adapter.py`

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/generate` | POST | Generate review from composed prompt (streaming) |
| `/api/tags` | GET | List available models |

**Streaming format assumption:** JSON lines, each `{"response": "...", "done": bool}`.
The adapter accumulates `response` fields across streaming lines. Don't change
the parsing without verifying against the current Ollama API spec.

### 2.4 Rate Limit Headers

Parsed by `RateLimitTracker` (`src/pr_auto_reviewer/infrastructure/client/rate_limit_tracker/rate_limit_tracker.py`).

| Header | GitHub | Forgejo |
|---|---|---|
| `x-ratelimit-limit` | ✅ | ✅ |
| `x-ratelimit-remaining` | ✅ | ✅ |
| `x-ratelimit-reset` | ✅ | ✅ |
| `x-ratelimit-resource` | ✅ | ❌ |

**DO NOT** rename these without checking that both platforms still send them.
Rate-limit state is persisted to disk — changing header names silently breaks
rate-limit tracking.

---

## 3. Critical Internal Contracts

### 3.1 Verdict-to-Event Mapping

**File:** `src/pr_auto_reviewer/infrastructure/review_publishers/_shared.py`

```python
_VERDICT_TO_EVENT: dict[ReviewVerdict, str] = {
    ReviewVerdict.APPROVED:          "APPROVE",
    ReviewVerdict.CHANGES_REQUESTED: "REQUEST_CHANGES",
    ReviewVerdict.COMMENTED:         "COMMENT",
}
```

This is the **single source of truth**. The three values are exhaustive by
design. Adding a fourth verdict is a breaking change — requires publisher
updates on both platforms and integration tests for the new path.

For the Forgejo `APPROVE → APPROVED` override, see
`ForgejoReviewPublisher.publish()`.

### 3.2 CodeReview Construction — Verdict Preservation

`CodeReview` is `frozen=True`. Every construction site is a potential verdict
mutation point. See `docs/verdict-event-mapping.md` §"Danger Zones" for the
complete table.

**The rule:** when constructing a `CodeReview` that passes through the LLM's
output, **always** use `verdict=review.verdict`, never hardcode.

The bug this branch fixed: `_add_deterministic_findings` in
`src/pr_auto_reviewer/application/services/review_pull_request_service.py`
hardcoded `verdict=ReviewVerdict.APPROVED`. Codeberg returned HTTP 500 when
the payload combined an `APPROVED` event with blocking inline comments.

### 3.3 ReviewPublishingService — POST Body Schema

**File:** `src/pr_auto_reviewer/infrastructure/review_publishers/review_publishing_service.py:87-153`

```python
{
    "event": verdict_event,      # "APPROVE"/"APPROVED"/"REQUEST_CHANGES"/"COMMENT"
    "body": body,                 # Markdown review body
    "commit_id": str(sha),       # HEAD commit SHA
    "comments": [...],            # Inline comment payloads (optional)
    "official": True,             # Forgejo only
}
```

**DO NOT** change field names or types. **DO NOT** add platform-specific
fields without a platform-conditional guard.

### 3.4 ChangesetFetcher — Sequential File Fetch

Both fetchers fetch file content **one file at a time**. There is no batch
endpoint on either platform. This is by design, not a bug.

**DO NOT** attempt to batch or parallelize without:
1. Confirming an upstream batch endpoint exists.
2. Understanding that parallel requests can trigger rate-limit exhaustion
   before the `RateLimitTracker` can back off.

### 3.5 ItemSeverity — Blocking Threshold

**File:** `src/pr_auto_reviewer/domain/value_objects/item_severity.py`

```python
class ItemSeverity(StrEnum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    INFO = "info"

    @property
    def is_blocking(self) -> bool:
        return self in (ItemSeverity.CRITICAL, ItemSeverity.MAJOR)
```

`CRITICAL` and `MAJOR` items trigger a formal review (`APPROVED` /
`CHANGES_REQUESTED`). `MINOR` and `INFO` items go via comment-only path.

**DO NOT** add or remove values from the `is_blocking` tuple without
understanding the full publisher flow in
`ReviewPublishingService.publish()`.

---

## 4. Things That Look Like Bugs But Aren't

| Symptom | Why it's correct |
|---|---|
| 28 HTTP requests for a 28-file PR | No batch endpoint exists; sequential fetch rate-limited per request |
| Forgejo sends `"APPROVED"`, GitHub sends `"APPROVE"` | Forgejo rejects `"APPROVE"`; override in `ForgejoReviewPublisher` |
| `official=True` only on Forgejo reviews | GitHub has no `official` field |
| Comment-only reviews → issue comments, not formal reviews | By design: no blocking items + `COMMENTED` verdict → comment path |
| `RateLimitTracker` writes to disk | Persists state across restarts to avoid re-hitting limits on startup |

---

## 5. When You CAN Change Things

- **Infrastructure adapters** — when an upstream API deprecates an endpoint
  (verified by official docs/changelog) or you're adding a new endpoint
  alongside the old one.
- **Domain entities** — when a new business requirement demands it *and* the
  change preserves backward compatibility with existing ports.
- **Application services** — when adding deterministic findings or
  pre/post-processing steps that don't change verdict or item semantics.

**Always** run the full test suite after any change:
```bash
python -m pytest tests/ -x -q
```
