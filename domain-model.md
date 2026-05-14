# Domain Model & Application Layer

> Derived from `watch-prs.sh` — migration target to Python with Hexagonal Architecture + DDD.

---

## Domain Layer

### Value Objects

Value Objects are immutable, identified by their **values**, and carry no lifecycle of their own.

---

#### `PullRequestId`

Composite identity of a pull request within a platform.

| Field | Type | Description |
|---|---|---|
| `repository` | `str` | Full repo path — e.g. `owner/repo` |
| `number` | `int` | PR number within the repository |

> **Why VO:** Two `PullRequestId`s with the same `repository` and `number` are the same thing. No lifecycle, no mutation.

---

#### `CommitSha`

Represents a specific, immutable snapshot of code.

| Field | Type | Description |
|---|---|---|
| `value` | `str` | Full 40-char SHA or abbreviated form |

> **Why VO:** A SHA is content-addressed — it is its own identity. Comparing two SHAs is comparing two values.

---

#### `PullRequestDiff`

Immutable snapshot of what changed in a PR at a specific commit.

| Field | Type | Description |
|---|---|---|
| `pr_id` | `PullRequestId` | Which PR this diff belongs to |
| `head_sha` | `CommitSha` | The commit this diff was fetched at |
| `diff_content` | `str` | Raw unified diff |
| `file_contents` | `dict[str, str]` | Full file contents keyed by path |
| `repository_structure` | `Optional[str]` | Tree representation of the repo |
| `conventions` | `Optional[str]` | Content of ARCHITECTURE.md / CONVENTIONS.md |

> **Why VO:** Represents a point-in-time snapshot. If the SHA changes, it is a different diff entirely — not the same object updated.

---

#### `ReviewVerdict`

Enumerated conclusion of a code review.

| Value | Meaning |
|---|---|
| `APPROVED` | The diff is ready to merge as-is |
| `CHANGES_REQUESTED` | The diff requires corrections before merge |
| `COMMENTED` | Observations posted with no blocking decision |

> **Why VO:** A verdict is a pure typed value. It holds no identity.
>
> **Note:** How each value maps to a platform-specific event (e.g. `APPROVED`, `REQUEST_CHANGES`, `COMMENT`) is an **adapter concern**. The domain only knows these three states.

---

#### `ItemSeverity`

Classification of how critical a review finding is.

| Value |
|---|
| `CRITICAL` |
| `MAJOR` |
| `MINOR` |
| `INFO` |

> **Why VO:** A label with no lifecycle.

---

#### `ReviewItem`

A single actionable finding produced by the AI review.

| Field | Type | Description |
|---|---|---|
| `number` | `int` | Sequential position within the review |
| `severity` | `ItemSeverity` | How critical the finding is |
| `category` | `str` | Type of finding — e.g. `security`, `style` |
| `file_path` | `Optional[str]` | File the finding refers to |
| `description` | `str` | Human-readable explanation |

> **Why VO:** Immutable finding. Two items with the same fields are identical. The `number` is positional (scoped to the review), not a persistent identity.

---

#### `CodeReview`

The complete, structured output produced by the LLM for a given diff.

| Field | Type | Description |
|---|---|---|
| `verdict` | `ReviewVerdict` | Overall conclusion |
| `summary` | `str` | Short prose summary |
| `items` | `list[ReviewItem]` | Ordered list of findings |
| `model_used` | `str` | Name of the model that produced the review |

> **Why VO:** A review is the *result* of running a model over a diff. It never mutates. A new commit → a new review, not an updated one.

---

#### `ReviewContext`

Supporting context passed alongside the diff to improve review quality.

| Field | Type | Description |
|---|---|---|
| `architecture_hint` | `str` | Detected architecture type — e.g. `hexagonal`, `unknown` |
| `conventions` | `Optional[str]` | Content of conventions file |
| `repository_structure` | `Optional[str]` | Tree structure of the repo |

> **Why VO:** Pure input data for prompt construction. No identity, no lifecycle.

---

#### `IssueCommand`

A parsed user intent extracted from a PR comment requesting issue creation.

| Field | Type | Description |
|---|---|---|
| `comment_id` | `str` | Source comment that contained the command |
| `item_numbers` | `list[int]` | Which review item numbers to turn into issues |

> **Why VO:** The command is derived from parsing a comment body. It is a description of intent, not a persistent record.

---

#### `CommentId`

Opaque identifier for a comment on a pull request.

| Field | Type | Description |
|---|---|---|
| `value` | `str` | Platform-assigned comment ID |

> **Why VO:** An identifier treated as a value for idempotency tracking — it never changes.

---

### Entities

Entities have a **stable identity** that persists across state changes and carry a meaningful lifecycle.

---

#### `PullRequest` *(Aggregate Root)*

The central aggregate. Tracks the review lifecycle for a single PR across polling cycles.

| Field | Type | Description |
|---|---|---|
| `id` | `PullRequestId` | Stable identity |
| `title` | `str` | PR title |
| `head_sha` | `CommitSha` | Current HEAD — changes when author pushes |
| `is_draft` | `bool` | Draft PRs are excluded from review |
| `reviews` | `list[CodeReview]` | All reviews produced for this PR |
| `processed_comment_ids` | `set[CommentId]` | Commands already acted upon (idempotency) |

**Domain behaviours:**

```python
def needs_review(self, sha: CommitSha) -> bool:
    """True when sha differs from the last reviewed commit."""

def add_review(self, review: CodeReview, sha: CommitSha) -> None:
    """Records a completed review and advances the reviewed sha."""

def mark_comment_processed(self, comment_id: CommentId) -> None:
    """Records that a command comment was handled."""

def is_comment_processed(self, comment_id: CommentId) -> bool:
    """Idempotency guard for command processing."""
```

> **Why Entity:** Its identity (`PullRequestId`) is stable across commits. Its state changes over time — `head_sha` advances, reviews accumulate, processed comments grow. This is the lifecycle the shell script tracks in `pr-reviews.json`.

---

#### `Issue`

A tracker issue created from a review finding on the remote platform.

| Field | Type | Description |
|---|---|---|
| `id` | `int` | Platform-assigned issue number |
| `repository` | `str` | Repo the issue belongs to |
| `title` | `str` | Auto-generated title |
| `body` | `str` | Structured body referencing the PR and review item |
| `source_pr_id` | `PullRequestId` | The PR that originated the issue |
| `source_item_number` | `int` | Which `ReviewItem` it was created from |

> **Why Entity:** An issue has a platform-assigned numeric ID that persists. It can be updated, closed, or linked — it lives beyond the review cycle that created it.

---

## Application Layer

Application Services orchestrate domain objects and delegate to outbound ports. They contain **no business logic** — only coordination.

---

### `ReviewPullRequestService`

**Responsibility:** Determine whether a PR needs review, run the LLM review through an outbound port, and post the formal review to the remote platform.

```
Input:  PullRequestId, CommitSha, title
Output: None (side effects: review posted to platform, state persisted)
```

**Flow:**

```
1. Load PullRequest from PullRequestRepository
   └─ If not found, create a new PullRequest entity

2. Call pr.needs_review(sha)
   └─ If already reviewed → delegate to ProcessIssueCommandsService and return

3. Fetch PullRequestDiff via `ChangesetFetcherPort` (outbound)

4. Build ReviewContext via `RepositoryContextPort` (outbound)
   └─ Fetches repo tree, detects architecture hint, loads conventions file

5. Call `LlmReviewPort.review(diff, context)` → CodeReview  (outbound)

6. Call `ReviewPublisherPort.publish(pr_id, review)` → void  (outbound)
   └─ Delivers the verdict and comment body to the remote platform

7. pr.add_review(code_review, sha)

8. PullRequestRepository.save(pr)

9. If verdict is APPROVED → delegate to ProcessIssueCommandsService
```

**Outbound ports used:**

| Port | Role |
|---|---|
| `PullRequestRepository` | Load and persist `PullRequest` aggregate |
| `ChangesetFetcherPort` | Fetch diff and full file contents for a PR |
| `RepositoryContextPort` | Fetch repo tree, detect architecture hint, load conventions |
| `LlmReviewPort` | Send prompt, receive `CodeReview` |
| `ReviewPublisherPort` | Post the formal review (verdict + body) to the remote platform |

---

### `ProcessIssueCommandsService`

**Responsibility:** Scan new PR comments for issue-creation commands, validate requested item numbers against the existing review, and create tracker issues on the remote platform.

```
Input:  PullRequestId, CommitSha
Output: None (side effects: issues created on platform, comments posted, state persisted)
```

**Flow:**

```
1. Load PullRequest from PullRequestRepository

2. Fetch latest CodeReview body via ReviewReaderPort.get_latest_review(pr_id)

3. Parse review body into list[ReviewItem] via ReviewItemParser (domain service)

4. Fetch new comments via CommentReaderPort.get_pr_comments(pr_id)

5. For each comment:
   a. pr.is_comment_processed(comment_id) → skip if true
   b. Parse IssueCommand from comment body via IssueCommandParser (domain service)
   c. Skip if no command found
   d. pr.mark_comment_processed(comment_id)
   e. Validate item_numbers against known ReviewItems
      └─ If any invalid → CommentPublisherPort.post_comment(pr_id, error_message)
      └─ If all valid → for each item:
            IssueTrackerPort.create_issue(repository, title, body) → Issue
            Collect created issue numbers

6. Post confirmation comment with created issue numbers via CommentPublisherPort

7. PullRequestRepository.save(pr)
```

**Outbound ports used:**

| Port | Role |
|---|---|
| `PullRequestRepository` | Load and persist `PullRequest` aggregate |
| `ReviewReaderPort` | Fetch the latest posted review body for a PR |
| `CommentReaderPort` | Fetch comments posted on a PR |
| `CommentPublisherPort` | Post reply comments on a PR |
| `IssueTrackerPort` | Create tracker issues on the remote platform |

---

## Port Summary (Outbound)

Ports are **pure domain interfaces**. They speak only domain types. No platform SDK, no HTTP client, no API concept leaks into a port definition. Each port has one or more **adapters** as implementations — a Forgejo adapter, a GitHub adapter, an Ollama adapter, a filesystem adapter — but the port itself is unaware of any of them.

| Port | Responsibility | Example adapters |
|---|---|---|
| `PullRequestRepository` | Persist and hydrate `PullRequest` aggregate | JSON file, SQLite, PostgreSQL |
| `ChangesetFetcherPort` | Fetch `PullRequestDiff` for a given PR and SHA | Forgejo adapter, GitHub adapter |
| `RepositoryContextPort` | Fetch repo tree, detect architecture, load conventions | Forgejo adapter, GitHub adapter |
| `LlmReviewPort` | Receive a `PullRequestDiff` + `ReviewContext`, return `CodeReview` | Ollama adapter, OpenAI adapter, Anthropic adapter |
| `ReviewPublisherPort` | Publish a `CodeReview` verdict and body to the remote platform | Forgejo adapter, GitHub adapter, GitLab adapter |
| `ReviewReaderPort` | Retrieve the latest published review body for a PR | Forgejo adapter, GitHub adapter |
| `CommentReaderPort` | Fetch comments posted on a PR | Forgejo adapter, GitHub adapter |
| `CommentPublisherPort` | Post a reply comment on a PR | Forgejo adapter, GitHub adapter |
| `IssueTrackerPort` | Create a tracker issue from a `ReviewItem` | Forgejo adapter, GitHub adapter, Jira adapter |

> The four comment/review ports (`ReviewReaderPort`, `CommentReaderPort`, `CommentPublisherPort`, `ReviewPublisherPort`) may be grouped into a single `GitHostPort` in implementations where the platform is unified. The split exists at the port level to honour ISP — each application service depends only on the operations it actually needs.

