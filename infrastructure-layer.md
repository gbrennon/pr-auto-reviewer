# Infrastructure Layer — Outbound Port Implementations

> Each adapter in this layer implements exactly one port interface defined in the
> application layer. Adapters are the **only place** where platform SDKs, HTTP
> clients, file I/O, and third-party APIs are allowed to appear.
>
> **Rule:** An adapter translates between the domain's language and the outside
> world. It never contains business logic. If a condition decides something about
> the domain, it belongs in the domain. If it decides how to format an HTTP
> request, it belongs here.

---

## Conventions

```
[port]  → method being implemented from the port interface
[http]  → outbound HTTP call to a remote platform API
[io]    → local file / disk operation
[map]   → data mapping from external shape to domain type (or vice versa)
[err]   → translates a platform/IO error into a domain exception
```

---

## 1. Persistence Adapter

### `JsonFilePullRequestRepository`

**Implements:** `PullRequestRepository`  
**Replaces:** The `STATE_FILE` (`runner-data/pr-reviews.json`) and all `load_state` / `mark_comment_processed` bash functions.

**Responsibility:** Serialize and deserialize the `PullRequest` aggregate to a local
JSON file. This is the simplest persistence adapter for the current use case (single
process, no concurrency). Can be swapped for a `SqlitePullRequestRepository` or
`PostgresPullRequestRepository` without touching any application or domain code.

---

#### File structure (internal, not a domain concern)

```json
{
  "reviewed": {
    "owner/repo/42": {
      "title": "Fix login bug",
      "head_sha": "abc1234...",
      "is_draft": false,
      "reviews": [
        {
          "verdict": "changes_requested",
          "summary": "...",
          "model_used": "code-review",
          "items": [
            {
              "number": 1,
              "severity": "major",
              "category": "security",
              "file_path": "src/auth.py",
              "description": "..."
            }
          ]
        }
      ],
      "processed_comment_ids": ["101", "204"]
    }
  }
}
```

---

#### Implementation notes

```
[port] find(pr_id: PullRequestId) -> Optional[PullRequest]
    [io]  Read and parse STATE_FILE
    [map] Build PullRequestId, CommitSha, ReviewVerdict, ItemSeverity, ReviewItem,
          CodeReview, CommentId from raw dict
          └─ Key missing → return None
          └─ JSON malformed → [err] raise RepositoryCorruptedError

[port] save(pr: PullRequest) -> None
    [io]  Read current STATE_FILE (full load to avoid overwriting concurrent keys)
    [map] Serialize PullRequest → dict using same schema above
    [io]  Write atomically: write to tmp file, then os.replace() → avoids partial writes
```

> **Atomic write:** Always write to a `.tmp` sibling file and use `os.replace()`.
> The shell script overwrites the file directly, which risks corruption on crash.
> This adapter fixes that.

---

---

## 2. Git Platform Adapters

All four git-platform ports (`ChangesetFetcherPort`, `RepositoryContextPort`,
`ReviewPublisherPort`, `ReviewReaderPort`, `CommentReaderPort`,
`CommentPublisherPort`, `IssueTrackerPort`) interact with the same remote
platform API. Each adapter is its own class implementing its own port.

A shared `GitPlatformHttpClient` is injected into each adapter as a thin HTTP
wrapper (auth headers, base URL, error handling). It is **not** a port — it is
an infrastructure utility shared among adapters of the same platform family.

```python
class GitPlatformHttpClient:
    """
    Thin HTTP client shared by all git platform adapters.
    Handles: base URL, Authorization header, response status assertion.
    Not a port. Never referenced outside the infrastructure layer.
    """
    def __init__(self, base_url: str, token: str) -> None: ...

    def get(self, path: str, **params) -> dict: ...
    def get_raw(self, path: str) -> str: ...
    def post(self, path: str, body: dict) -> dict: ...
```

> Concrete implementations: `ForgejoHttpClient`, `GithubHttpClient`, etc.
> They extend or wrap `GitPlatformHttpClient` with platform-specific quirks
> (pagination shape, auth scheme, rate limiting).

---

### `GitChangesetFetcherAdapter`

**Implements:** `ChangesetFetcherPort`  
**Replaces:** `get_diff()`, `get_files_from_diff()`, `get_file_contents()`,
`forgejo_get_file_content()` bash functions.

```
[port] fetch(pr_id: PullRequestId, sha: CommitSha) -> PullRequestDiff
    [http] GET /repos/{repo}/pulls/{number}.diff
           └─ empty or < 50 chars → [err] raise EmptyDiffError(pr_id)
    [map]  Parse diff lines to extract changed file paths
    [http] For each changed file path:
               GET /repos/{repo}/raw/{sha}/{file_path}
               └─ 404 → skip file silently (deleted files have no content)
    [map]  Build PullRequestDiff(
               pr_id=pr_id,
               head_sha=sha,
               diff_content=raw_diff,
               file_contents={path: content, ...}
           )
```

> `repository_structure` and `conventions` are intentionally left to
> `RepositoryContextPort` — they are context, not changeset.

---

### `GitRepositoryContextAdapter`

**Implements:** `RepositoryContextPort`  
**Replaces:** `forgejo_get_repo_tree()`, `generate_repo_structure.py --detect-type-from-tree`,
and the conventions file loop in `process_pr()`.

```
[port] fetch(pr_id: PullRequestId) -> ReviewContext
    [http] GET /repos/{repo}/git/trees/main?recursive=1
           └─ failure → architecture_hint = "unknown", repository_structure = None

    [map]  Pass tree blob to ArchitectureDetector (infrastructure utility, not a port)
           └─ Inspects file paths for known layout patterns
              (e.g. src/domain/, src/application/ → "hexagonal")
           └─ Returns architecture_hint: str

    [http] Try each conventions filename in order:
               ARCHITECTURE.md → CONVENTIONS.md → .architecturerc
               GET /repos/{repo}/raw/main/{filename}
               └─ 200 → use content, stop loop
               └─ 404 → try next
               └─ all missing → conventions = None

    [map]  Build ReviewContext(
               architecture_hint=architecture_hint,
               conventions=conventions,
               repository_structure=tree_as_string
           )
```

---

### `GitReviewPublisherAdapter`

**Implements:** `ReviewPublisherPort`  
**Replaces:** The `post_review()` bash function — reviewer request + formal review POST.

```
[port] publish(pr_id: PullRequestId, review: CodeReview) -> None
    [map]  verdict_event = VerdictMapper.to_platform_event(review.verdict)
           # APPROVED → "APPROVED" | CHANGES_REQUESTED → "REQUEST_CHANGES" | COMMENTED → "COMMENT"
           # VerdictMapper is a private adapter utility — mapping lives here, never in the domain

    [map]  body = ReviewBodyFormatter.format(review)
           # Renders summary + numbered items into markdown
           # ReviewBodyFormatter is a private adapter utility

    [http] POST /repos/{repo}/pulls/{number}/requested_reviewers
               body: {"reviewers": [reviewer_username]}
               └─ failure is non-fatal: log and continue

    [http] POST /repos/{repo}/pulls/{number}/reviews
               body: {"event": verdict_event, "body": body}
               └─ non-2xx → [err] raise ReviewPublishError(pr_id, status_code)
```

> `reviewer_username` and `reviewer_token` come from config injected at
> construction time — never from the domain or the application service.

---

### `GitReviewReaderAdapter`

**Implements:** `ReviewReaderPort`  
**Replaces:** `get_pr_reviews()`, `get_latest_review()` bash functions.

```
[port] get_latest_review(pr_id: PullRequestId) -> Optional[str]
    [http] GET /repos/{repo}/pulls/{number}/reviews?limit=10
    [map]  Parse response list, sort by submitted_at descending
           └─ empty list → return None
    [map]  Return body string of the most recent review entry
```

---

### `GitCommentReaderAdapter`

**Implements:** `CommentReaderPort`  
**Replaces:** `get_pr_comments()` bash function + `get_pr_comments.py`.

```
[port] get_comments(pr_id: PullRequestId) -> list[PrComment]
    [http] GET /repos/{repo}/issues/{number}/comments?limit=50
    [map]  For each entry in response:
               Build PrComment(
                   id=CommentId(str(entry["id"])),
                   body=entry["body"],
                   created_at=datetime.fromisoformat(entry["created_at"])
               )
    [map]  Return list sorted by created_at ascending
           └─ empty → return []
```

---

### `GitCommentPublisherAdapter`

**Implements:** `CommentPublisherPort`  
**Replaces:** The inline `curl POST .../comments` calls scattered across `process_issue_commands()`.

```
[port] post(pr_id: PullRequestId, body: str) -> None
    [http] POST /repos/{repo}/issues/{number}/comments
               body: {"body": body}
               └─ non-2xx → log warning; do not raise
                  (comment posting failure is non-fatal — issues were already created)
```

---

### `GitIssueTrackerAdapter`

**Implements:** `IssueTrackerPort`  
**Replaces:** `create_issue()` bash function.

```
[port] create(repository: str, title: str, body: str) -> Issue
    [http] POST /repos/{repository}/issues
               body: {"title": title, "body": body}
               └─ non-2xx → [err] raise IssueCreationError(repository, title, status_code)
    [map]  Build Issue(
               id=response["number"],
               repository=repository,
               title=title,
               body=body,
               source_pr_id=...,   # not available here; caller sets it if needed
               source_item_number=...
           )
           └─ Return Issue
```

> `Issue` fields `source_pr_id` and `source_item_number` are set by the
> application service before persisting if traceability is required. The adapter
> only knows what the platform returned.

---

---

## 3. LLM Adapter

### `OllamaLlmAdapter`

**Implements:** `LlmReviewPort`  
**Replaces:** The Ollama `curl` call in `process_pr()`, `build_prompt.py`,
`build_comment.py`, and `ollama-client.sh`.

**Responsibility:** Build the prompt from domain objects, send it to Ollama,
parse the raw text response into a `CodeReview`.

```
[port] review(diff: PullRequestDiff, context: ReviewContext) -> CodeReview
    [map]  prompt = PromptBuilder.build(diff, context)
           # PromptBuilder is a private adapter utility — prompt engineering lives here.
           # It has access to diff_content, file_contents, architecture_hint,
           # conventions, repository_structure.

    [http] POST {ollama_host}/api/generate
               body: {"model": model_name, "prompt": prompt, "stream": false}
               └─ network error / non-2xx → [err] raise LlmUnavailableError(model_name)

    [map]  raw_text = response["response"]
           └─ empty → [err] raise LlmUnavailableError(model_name)

    [map]  code_review = ReviewResponseParser.parse(raw_text, model_used=model_name)
           # ReviewResponseParser is a private adapter utility.
           # Parses the structured markdown/JSON the model was prompted to return.
           # Maps to CodeReview(verdict, summary, items=[ReviewItem(...)], model_used)
           └─ parse failure → [err] raise LlmResponseMalformedError(raw_text)

    return code_review
```

#### Private utilities (adapter-internal, not ports)

| Utility | Responsibility |
|---|---|
| `PromptBuilder` | Assembles the full prompt string from `PullRequestDiff` + `ReviewContext` |
| `ReviewResponseParser` | Parses raw LLM text output into a `CodeReview` domain object |

> Other LLM adapters (`OpenAiLlmAdapter`, `AnthropicLlmAdapter`) implement the
> same port and provide their own `PromptBuilder` / `ReviewResponseParser`
> variants. The application service is unaffected.

---

---

## Adapter Summary

| Adapter | Port implemented | Platform |
|---|---|---|
| `JsonFilePullRequestRepository` | `PullRequestRepository` | Local filesystem |
| `GitChangesetFetcherAdapter` | `ChangesetFetcherPort` | Any Forgejo/GitHub-compatible API |
| `GitRepositoryContextAdapter` | `RepositoryContextPort` | Any Forgejo/GitHub-compatible API |
| `GitReviewPublisherAdapter` | `ReviewPublisherPort` | Any Forgejo/GitHub-compatible API |
| `GitReviewReaderAdapter` | `ReviewReaderPort` | Any Forgejo/GitHub-compatible API |
| `GitCommentReaderAdapter` | `CommentReaderPort` | Any Forgejo/GitHub-compatible API |
| `GitCommentPublisherAdapter` | `CommentPublisherPort` | Any Forgejo/GitHub-compatible API |
| `GitIssueTrackerAdapter` | `IssueTrackerPort` | Any Forgejo/GitHub-compatible API |
| `OllamaLlmAdapter` | `LlmReviewPort` | Ollama |

---

## What the Infrastructure Layer Must Never Do

- Import from `application` or `domain` layers to make decisions — it only
  translates between those layers and the outside world.
- Contain conditionals that encode business rules (e.g. "skip if severity is INFO").
- Call another adapter directly — adapters are always composed by the application
  service or the dependency injection container, never by each other.
- Return raw platform types (dicts, JSON strings) to the application layer — always
  map to domain or application types before returning.
- Raise platform-specific exceptions beyond its own boundary — translate them to
  domain exceptions (`LlmUnavailableError`, `ReviewPublishError`, etc.) at the
  adapter boundary.
