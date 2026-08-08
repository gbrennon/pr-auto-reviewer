# Verdict ↔ Event Mapping (Git Host Review APIs)

Canonical reference for how `ReviewVerdict` maps to each git host's PR review API event.

---

## Domain Verdicts

Defined in `src/pr_auto_reviewer/domain/value_objects/review_verdict.py`:

| `ReviewVerdict` | String value | Meaning |
|---|---|---|
| `APPROVED` | `"approved"` | PR is acceptable as-is |
| `CHANGES_REQUESTED` | `"changes_requested"` | Blocking issues found; PR must not be merged |
| `COMMENTED` | `"commented"` | Non-blocking feedback only |

---

## Canonical Mapping → Platform Events

Defined in `src/pr_auto_reviewer/infrastructure/review_publishers/_shared.py`:

```python
_VERDICT_TO_EVENT: dict[ReviewVerdict, str] = {
    ReviewVerdict.APPROVED:          "APPROVE",
    ReviewVerdict.CHANGES_REQUESTED: "REQUEST_CHANGES",
    ReviewVerdict.COMMENTED:         "COMMENT",
}
```

This is the **GitHub API** naming convention. GitHub's review endpoint expects:
- `APPROVE` (not `APPROVED`)
- `REQUEST_CHANGES`
- `COMMENT`

### Forgejo/Codeberg Override

Forgejo diverges from GitHub on the approve event name. The override is applied in
`ForgejoReviewPublisher.publish()` (line 42–43):

```python
verdict_event = _VERDICT_TO_EVENT.get(review.verdict, "COMMENT")
if verdict_event == "APPROVE":
    verdict_event = "APPROVED"   # Forgejo uses APPROVED, not APPROVE
```

Forgejo/Codeberg expects:
- `APPROVED` (not `APPROVE`)
- `REQUEST_CHANGES`
- `COMMENT`

---

## Publisher Behavior by Verdict

| Verdict | GitHub event | Forgejo event | Published as | Item placement |
|---|---|---|---|---|
| `APPROVED` | `APPROVE` | `APPROVED` | Formal review | All items in review body; no separate comment |
| `CHANGES_REQUESTED` | `REQUEST_CHANGES` | `REQUEST_CHANGES` | Formal review + optional comment | **GitHub**: all items in review body. **Forgejo**: blocking items (CRITICAL/MAJOR) in review body; non-blocking items (MINOR/INFO) as a separate PR comment |
| `COMMENTED` | `COMMENT` | `COMMENT` | Plain PR comment | All items in a single comment (both platforms) |

### Critical Rule

> **APPROVED reviews MUST NOT carry blocking inline comments.**
> Both GitHub and Forgejo/Codeberg reject this combination (HTTP 422 or 500).

The publisher enforces this: a `COMMENT` verdict is published as a plain comment
(not a review), and only `CHANGES_REQUESTED` / `APPROVED` trigger formal reviews.
For `APPROVED`, blocking items are logically empty because the LLM wouldn't
return blocking items alongside an approve verdict.


### Blocking/Non-Blocking Split

The `ReviewPublisherProcessor._build_formal_path()` method controls whether
non-blocking items (MINOR/INFO) are split into a separate comment. The split
is platform-dependent:

- **GitHub** (`GithubReviewPublisher`): all items stay in the formal review
  body — no separate comment is posted.
- **Forgejo** (`ForgejoReviewPublisher`): blocking items go into the formal
  review; non-blocking items are published as a separate PR comment with a
  `COMMENTED`-style body (no verdict header).

The `COMMENTED` verdict path (`_build_comment_path`) is unchanged — it always
emits a single comment containing all items, regardless of platform.
---

## Danger Zones: Places That Construct `CodeReview`

Any code that creates a new `CodeReview` object is a **verdict mutation point**.
These are the places where a verdict can be accidentally overwritten:

| Location | Line (approx.) | What it does | Risk |
|---|---|---|---|
| `review_pull_request_service.py` `_add_deterministic_findings` | ~282 | Adds noisy-logging findings; **MUST preserve `review.verdict`** | HIGH — was hardcoded `APPROVED`, now fixed |
| `review_pull_request_service.py` execute guard | ~96 | Overrides to `CHANGES_REQUESTED` when prior unresolved blockers exist | LOW — intentional, guarded by `if` |
| `forgejo_review_publisher.py` `publish` | ~42,56 | Splits items into comment/review body; applies `APPROVED`→`APPROVE` override | LOW — copies input verdict |
| `github_review_publisher.py` `publish` | ~42,56 | Same pattern as Forgejo (no event-name override needed) | LOW — copies input verdict |

> **Note**: Line numbers are approximate and drift with refactors. Use `grep` to
> locate the current positions: `grep -n "def publish\|_add_deterministic"` in the
> relevant source files.

### Agent Checklist: When Touching `CodeReview` Construction

1. **NEVER hardcode `verdict=ReviewVerdict.APPROVED`** — always pass through the
   LLM's actual verdict unless an explicit guard (like unresolved blockers) demands
   an override.

2. **If you add a new site that constructs `CodeReview`**, add it to the table above.

3. **If you add a new verdict value to `ReviewVerdict`**, update:
   - `_VERDICT_TO_EVENT` in `_shared.py`
   - The Forgejo `APPROVE → APPROVED` override if applicable
   - This document's mapping tables

---

## API Response Codes

| Scenario | GitHub | Forgejo/Codeberg |
|---|---|---|
| Valid review | 200 | 200 |
| APPROVED with blocking inline comments | 422 | **500** (misleading — the error message is empty) |
| Missing token scopes | 403 | 403 |
| PR not found | 404 | 404 |

Note: Codeberg returns HTTP 500 for an invalid review payload (APPROVED + blocking
comments) instead of 422. The response body is `{"message":"","url":"..."}` —
the empty message makes this hard to diagnose from logs alone.

---

## How We Got Here

2026-07-19: PR #100 failed with HTTP 500 on Codeberg. Trace:

1. LLM returned `CHANGES_REQUESTED` (4 issues, some blocking)
2. `_add_deterministic_findings` detected noisy `logger.info` calls in the diff
3. It constructed a new `CodeReview` with **hardcoded `verdict=ReviewVerdict.APPROVED`**
4. Forgejo publisher mapped this to event `APPROVED`
5. `POST /reviews` with `APPROVED` + blocking inline comments → HTTP 500

Fix: line 282 changed from `verdict=ReviewVerdict.APPROVED` to `verdict=review.verdict`.
