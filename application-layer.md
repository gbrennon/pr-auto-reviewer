# Application Layer

> This layer will be located in a dir named core. It represents domain and application layers.
> This document details the application services, their commands, outbound port contracts,
> and the domain services they delegate business parsing to.
>
> **Principle:** Application services contain **no business logic**. They own only
> orchestration — loading aggregates, calling ports, persisting state. Every rule
> that decides something belongs to the domain.

---

## Conventions

```
[in]  → inbound (what enters the service)
[out] → outbound port call
[dom] → domain object / domain service call (pure, no I/O)
[err] → raises a domain exception; caller handles it
```

All application services receive their dependencies via **constructor injection**.
Ports are injected as abstract interfaces; no concrete adapter is referenced.

---

## Application Services

### 1. `ReviewPullRequestService`

**Use case:** A PR has been detected as new or updated. Fetch its changeset, run
it through the LLM, and publish the resulting review to the remote platform.

---

#### Command

```python
@dataclass(frozen=True)
class ReviewPullRequestCommand:
    pr_id: PullRequestId
    head_sha: CommitSha
    title: str
```

> The command is the only coupling point between the inbound adapter (the poller,
> a CLI trigger, a webhook handler) and the application service. The adapter
> constructs it from whatever data the platform delivers; the service never
> touches a raw HTTP response or env var.

---

#### Constructor dependencies

```python
class ReviewPullRequestService:
    def __init__(
        self,
        pr_repository: PullRequestRepository,
        changeset_fetcher: ChangesetFetcherPort,
        repository_context: RepositoryContextPort,
        llm_review: LlmReviewPort,
        review_publisher: ReviewPublisherPort,
        process_issue_commands: ProcessIssueCommandsService,  # delegated after APPROVED
    ) -> None:
```

---

#### Execution flow

```
[in]  command: ReviewPullRequestCommand

1.  [out] pr = PullRequestRepository.find(command.pr_id)
          └─ None → [dom] pr = PullRequest.create(command.pr_id, command.title, command.head_sha)

2.  [dom] pr.needs_review(command.head_sha)
          └─ False → [out] PullRequestRepository.save(pr)
                   → delegate to ProcessIssueCommandsService
                   → return   # idempotency guard: same SHA already reviewed

3.  [out] diff: PullRequestDiff = ChangesetFetcherPort.fetch(command.pr_id, command.head_sha)
          └─ empty diff → [err] raise EmptyDiffError(command.pr_id)

4.  [out] context: ReviewContext = RepositoryContextPort.fetch(command.pr_id)
          └─ failure is non-fatal; context fields default to None/unknown

5.  [out] review: CodeReview = LlmReviewPort.review(diff, context)

6.  [out] ReviewPublisherPort.publish(command.pr_id, review)

7.  [dom] pr.add_review(review, command.head_sha)

8.  [out] PullRequestRepository.save(pr)

9.  review.verdict == APPROVED
          └─ True  → delegate to ProcessIssueCommandsService
          └─ False → return   # CHANGES_REQUESTED or COMMENTED: no issue commands expected
```

---

#### Raised exceptions

| Exception | Condition | Who handles it |
|---|---|---|
| `EmptyDiffError` | Diff fetched but has no content | Inbound adapter — logs and skips the PR |
| `LlmUnavailableError` | LLM port unreachable or timed out | Inbound adapter — logs and retries next cycle |
| `ReviewPublishError` | Platform rejected the review POST | Inbound adapter — logs; state is NOT saved so the PR retries |

> **Important:** `PullRequestRepository.save` is called **after** `ReviewPublisherPort.publish`
> succeeds. If publish fails the aggregate is not saved, so the next polling cycle
> will retry the full review. This is intentional at-least-once delivery.

---

#### Outbound port contracts

##### `PullRequestRepository`

```python
class PullRequestRepository(ABC):
    @abstractmethod
    def find(self, pr_id: PullRequestId) -> Optional[PullRequest]: ...

    @abstractmethod
    def save(self, pr: PullRequest) -> None: ...
```

##### `ChangesetFetcherPort`

```python
class ChangesetFetcherPort(ABC):
    @abstractmethod
    def fetch(self, pr_id: PullRequestId, sha: CommitSha) -> PullRequestDiff: ...
```

##### `RepositoryContextPort`

```python
class RepositoryContextPort(ABC):
    @abstractmethod
    def fetch(self, pr_id: PullRequestId) -> ReviewContext: ...
```

> Implementations fetch the repo tree, detect the architecture hint, and look for
> a conventions file (`ARCHITECTURE.md`, `CONVENTIONS.md`, `.architecturerc`).
> None of that logic belongs here.

##### `LlmReviewPort`

```python
class LlmReviewPort(ABC):
    @abstractmethod
    def review(self, diff: PullRequestDiff, context: ReviewContext) -> CodeReview: ...
```

> The adapter is responsible for prompt construction, raw response parsing,
> and mapping the LLM output into a `CodeReview`. The service receives only
> a fully-formed domain object.

##### `ReviewPublisherPort`

```python
class ReviewPublisherPort(ABC):
    @abstractmethod
    def publish(self, pr_id: PullRequestId, review: CodeReview) -> None: ...
```

> The adapter translates `ReviewVerdict` into whatever event string the target
> platform expects, requests a reviewer if required, and posts the body.
> None of that is visible to the service.

---

---

### 2. `ProcessIssueCommandsService`

**Use case:** After a review is posted (or on every polling cycle for already-reviewed
PRs), scan new comments for issue-creation commands, validate the requested item
numbers, and create tracker issues for each valid one.

---

#### Command

```python
@dataclass(frozen=True)
class ProcessIssueCommandsCommand:
    pr_id: PullRequestId
    head_sha: CommitSha
```

---

#### Constructor dependencies

```python
class ProcessIssueCommandsService:
    def __init__(
        self,
        pr_repository: PullRequestRepository,
        review_reader: ReviewReaderPort,
        comment_reader: CommentReaderPort,
        comment_publisher: CommentPublisherPort,
        issue_tracker: IssueTrackerPort,
        review_item_parser: ReviewItemParser,      # domain service
        issue_command_parser: IssueCommandParser,  # domain service
    ) -> None:
```

---

#### Execution flow

```
[in]  command: ProcessIssueCommandsCommand

1.  [out] pr = PullRequestRepository.find(command.pr_id)
          └─ None → [err] raise PullRequestNotFoundError(command.pr_id)

2.  [out] raw_body: str = ReviewReaderPort.get_latest_review(command.pr_id)
          └─ empty → return   # no review posted yet; nothing to parse

3.  [dom] review_items: list[ReviewItem] = ReviewItemParser.parse(raw_body)
          └─ empty → return   # review has no actionable items

4.  [out] comments: list[PrComment] = CommentReaderPort.get_comments(command.pr_id)
          └─ empty → return   # no comments to process

5.  for each comment in comments:

    5a. [dom] pr.is_comment_processed(comment.id)
              └─ True → continue   # idempotency: already handled

    5b. [dom] command: Optional[IssueCommand] = IssueCommandParser.parse(comment.body)
              └─ None → continue   # no command syntax found in this comment

    5c. [dom] pr.mark_comment_processed(comment.id)

    5d. [dom] valid, invalid = partition(command.item_numbers, against=review_items)

    5e. invalid not empty:
              [out] CommentPublisherPort.post(
                        command.pr_id,
                        body=InvalidItemsMessage(invalid, available=review_items)
                    )
              continue

    5f. created_issues: list[Issue] = []
        for each item_number in valid:
            [dom] item = review_items.find(item_number)
            [dom] title, body = IssueBodyBuilder.build(pr_id=command.pr_id, item=item)
            [out] issue: Issue = IssueTrackerPort.create(command.pr_id.repository, title, body)
            created_issues.append(issue)

    5g. created_issues not empty:
              [out] CommentPublisherPort.post(
                        command.pr_id,
                        body=IssuesCreatedMessage(created_issues)
                    )

6.  [out] PullRequestRepository.save(pr)
```

---

#### Raised exceptions

| Exception | Condition | Who handles it |
|---|---|---|
| `PullRequestNotFoundError` | Aggregate not in repository | Inbound adapter — should not happen in normal flow; logged as error |
| `IssueCreationError` | Tracker port failed to create an issue | Caught per-item inside the loop — logs and continues to next item |

> `PullRequestRepository.save` is always called at the end even if some issue
> creations failed. The processed comment IDs are persisted regardless, preventing
> double-processing on retry.

---

#### Domain services used

##### `ReviewItemParser`

```python
class ReviewItemParser:
    def parse(self, raw_body: str) -> list[ReviewItem]: ...
```

Pure domain service. Receives the markdown body of a posted review and returns
the structured `ReviewItem` list. Contains all parsing rules — no I/O, no ports.

##### `IssueCommandParser`

```python
class IssueCommandParser:
    def parse(self, comment_body: str) -> Optional[IssueCommand]: ...
```

Pure domain service. Detects the command syntax in a comment (e.g. `/create-issue 1,3`)
and returns an `IssueCommand` VO, or `None` if no command is present.

##### `IssueBodyBuilder`

```python
class IssueBodyBuilder:
    def build(self, pr_id: PullRequestId, item: ReviewItem) -> tuple[str, str]: ...
```

Pure domain service. Produces the `(title, body)` for a tracker issue from a
`ReviewItem`. The template is a domain rule — it references PR number, severity,
category, file path, and description. No platform formatting leaks in here.

---

#### Outbound port contracts

##### `ReviewReaderPort`

```python
class ReviewReaderPort(ABC):
    @abstractmethod
    def get_latest_review(self, pr_id: PullRequestId) -> Optional[str]: ...
```

> Returns the raw markdown body of the most recently posted review, or `None`
> if no review has been published yet.

##### `CommentReaderPort`

```python
@dataclass(frozen=True)
class PrComment:
    id: CommentId
    body: str
    created_at: datetime

class CommentReaderPort(ABC):
    @abstractmethod
    def get_comments(self, pr_id: PullRequestId) -> list[PrComment]: ...
```

> `PrComment` is an application-layer DTO — it carries only what the service
> needs. The adapter maps from whatever the platform returns.

##### `CommentPublisherPort`

```python
class CommentPublisherPort(ABC):
    @abstractmethod
    def post(self, pr_id: PullRequestId, body: str) -> None: ...
```

##### `IssueTrackerPort`

```python
class IssueTrackerPort(ABC):
    @abstractmethod
    def create(self, repository: str, title: str, body: str) -> Issue: ...
```

---

## Shared Port

`PullRequestRepository` is shared between both services. It is injected into each
independently — they do not share a runtime instance, but they share the same
interface and the same underlying adapter.

```python
class PullRequestRepository(ABC):
    @abstractmethod
    def find(self, pr_id: PullRequestId) -> Optional[PullRequest]: ...

    @abstractmethod
    def save(self, pr: PullRequest) -> None: ...
```

---

## Dependency Graph

```
Inbound adapter (poller / CLI / webhook)
    │
    ├─► ReviewPullRequestService
    │       ├─► PullRequestRepository
    │       ├─► ChangesetFetcherPort
    │       ├─► RepositoryContextPort
    │       ├─► LlmReviewPort
    │       ├─► ReviewPublisherPort
    │       └─► ProcessIssueCommandsService ──────────────────────┐
    │                                                              │
    └─► ProcessIssueCommandsService  ◄─────────────────────────────┘
            ├─► PullRequestRepository
            ├─► ReviewReaderPort
            ├─► CommentReaderPort
            ├─► CommentPublisherPort
            ├─► IssueTrackerPort
            ├─► ReviewItemParser      (domain service, pure)
            ├─► IssueCommandParser    (domain service, pure)
            └─► IssueBodyBuilder      (domain service, pure)
```

> `ProcessIssueCommandsService` can be called directly by the inbound adapter
> (for already-reviewed PRs) or delegated to by `ReviewPullRequestService`
> (immediately after an APPROVED review). In both cases it receives the same
> command type and behaves identically.

---

## What the Application Layer Must Never Do

- Instantiate domain objects with knowledge of platform internals.
- Parse raw HTTP responses, JSON bodies, or env vars.
- Contain conditionals that encode business rules (e.g. "only create issues if severity is CRITICAL").
- Call one port to decide which other port to call.
- Bypass the aggregate — every state mutation goes through `PullRequest` methods.
