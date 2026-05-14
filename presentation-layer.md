# Presentation Layer — Inbound Adapters

> The presentation layer is the **entry point** of the system. It drives the
> application layer by constructing commands and invoking application services.
> It is the only layer allowed to know about the outside trigger — a cron tick,
> a CLI argument, a webhook HTTP request.
>
> **Rule:** Inbound adapters contain no business logic and no domain knowledge
> beyond constructing commands. If a condition decides something about the domain,
> it does not belong here.

---

## Conventions

```
[env]   → reads from environment variable or config file
[arg]   → reads from CLI argument
[http]  → inbound HTTP request (webhook mode)
[cmd]   → constructs and dispatches an application command
[log]   → structured log output (not print statements)
[err]   → catches a domain or application exception and handles it at the boundary
```

---

## Inbound Adapters

### 1. `PollingDaemon`

**Drives:** `ReviewPullRequestService`, `ProcessIssueCommandsService`  
**Replaces:** The main `cycle()` loop, `get_repos()`, `get_open_prs()`, and the
`while true; do ... sleep; done` shell loop.

**Responsibility:** On each tick, discover all open non-draft PRs across watched
repositories and dispatch a `ReviewPullRequestCommand` for each one.

---

#### Configuration

```python
@dataclass(frozen=True)
class PollingDaemonConfig:
    poll_interval_seconds: int        # env: POLL_INTERVAL, default 60
    repos_filter: Optional[str]       # env: REPOS_FILTER — "owner/repo" or None (all)
    run_once: bool                    # flag: --once
```

> Config is assembled by the composition root, not by the daemon itself.
> The daemon receives a fully built config object.

---

#### Constructor dependencies

```python
class PollingDaemon:
    def __init__(
        self,
        config: PollingDaemonConfig,
        repo_lister: RepoListerPort,           # inbound-side port: lists repos to watch
        pr_lister: PrListerPort,               # inbound-side port: lists open PRs per repo
        review_service: ReviewPullRequestService,
    ) -> None:
```

> `RepoListerPort` and `PrListerPort` are **inbound-side ports** — they exist to
> keep the daemon testable without hitting the network. Their adapters
> (`GitRepoListerAdapter`, `GitPrListerAdapter`) live in the infrastructure layer
> alongside the outbound adapters.

---

#### Inbound-side port contracts

##### `RepoListerPort`

```python
class RepoListerPort(ABC):
    @abstractmethod
    def list_repos(self) -> list[str]: ...
    # Returns full repo paths: ["owner/repo-a", "owner/repo-b"]
    # Respects repos_filter if configured at adapter level
```

##### `PrListerPort`

```python
@dataclass(frozen=True)
class OpenPullRequest:
    pr_id: PullRequestId
    head_sha: CommitSha
    title: str
    is_draft: bool

class PrListerPort(ABC):
    @abstractmethod
    def list_open(self, repository: str) -> list[OpenPullRequest]: ...
```

> `OpenPullRequest` is a presentation-layer DTO. It carries exactly what the
> daemon needs to build a command. The adapter maps from the platform response.

---

#### Execution flow

```
loop every poll_interval_seconds (or once if run_once=True):

1.  [cmd]  repos = RepoListerPort.list_repos()
           └─ empty → [log] warn "no repos found"; continue to next tick

2.  for each repo in repos:
    2a. [cmd]  open_prs = PrListerPort.list_open(repo)
               └─ empty → [log] debug "no open PRs in {repo}"; continue

    2b. for each pr in open_prs:
        └─ pr.is_draft → [log] debug "skipping draft PR #{pr.id.number}"; skip

        [cmd]  command = ReviewPullRequestCommand(
                   pr_id=pr.pr_id,
                   head_sha=pr.head_sha,
                   title=pr.title,
               )

        [cmd]  review_service.execute(command)
               [err] EmptyDiffError       → [log] warn "empty diff, skipping PR #{number}"
               [err] LlmUnavailableError  → [log] error "LLM unavailable, will retry next cycle"
               [err] ReviewPublishError   → [log] error "publish failed for PR #{number}"
               [err] any unexpected error → [log] error with traceback; continue loop

3.  if run_once → exit
    else → sleep(poll_interval_seconds) → goto 1
```

---

#### Signals and lifecycle

```
SIGINT / SIGTERM → graceful shutdown: finish current cycle, then exit
                   [replaces: trap EXIT INT TERM in the shell script]

Lock file        → acquired at startup; released on exit
                   [replaces: flock + PID file management]
                   Implementation: use a LockFileManager utility in the
                   infrastructure layer, called from the composition root.
```

---

---

### 2. `CliRunner`

**Drives:** `ReviewPullRequestService`, `ProcessIssueCommandsService`  
**Replaces:** The `-p <pr-number>` (force re-review) and `--list-items` CLI flags.

**Responsibility:** Provide operator commands for manual triggering, debugging,
and administration without running the full daemon loop.

---

#### Sub-commands

##### `review`

Force a review of a specific PR, bypassing the SHA-based idempotency guard.

```
Usage: cli review --repo <owner/repo> --pr <number>

[arg]  repo: str, pr_number: int
[cmd]  Fetch current HEAD SHA via PrListerPort.list_open(repo)
       └─ PR not found → print error; exit 1
[cmd]  command = ReviewPullRequestCommand(pr_id, head_sha, title)
[cmd]  review_service.execute(command)
       [err] any error → print error message; exit 1
[log]  Print "Review posted for PR #{number}"
```

##### `process-commands`

Manually trigger issue-command processing for a specific PR.

```
Usage: cli process-commands --repo <owner/repo> --pr <number>

[arg]  repo: str, pr_number: int
[cmd]  pr_id = PullRequestId(repository=repo, number=pr_number)
[cmd]  Fetch current HEAD SHA via PrListerPort
[cmd]  command = ProcessIssueCommandsCommand(pr_id, head_sha)
[cmd]  process_issue_commands_service.execute(command)
       [err] PullRequestNotFoundError → print "PR not in local state"; exit 1
       [err] any error → print error message; exit 1
[log]  Print "Command processing complete"
```

##### `list-items`

Print the parsed review items of the latest posted review for a PR.
Useful for debugging `ReviewItemParser` output without creating issues.

```
Usage: cli list-items --repo <owner/repo> --pr <number>

[arg]  repo: str, pr_number: int
[cmd]  pr_id = PullRequestId(repository=repo, number=pr_number)
[out]  raw_body = ReviewReaderPort.get_latest_review(pr_id)
       └─ None → print "No review found for PR #{number}"; exit 1
[dom]  items = ReviewItemParser.parse(raw_body)
       └─ empty → print "No actionable items found"; exit 0
[log]  Print formatted table:
           #  | Severity | Category | File                  | Description
           1  | MAJOR    | security | src/auth.py           | ...
           2  | MINOR    | style    | src/utils.py          | ...
```

> `list-items` calls `ReviewReaderPort` and `ReviewItemParser` directly — it does
> not go through an application service because it is a read-only inspection tool,
> not a use-case.

---

#### CLI construction

```python
# Entry point wired in composition root
import argparse

def build_cli(
    review_service: ReviewPullRequestService,
    process_commands_service: ProcessIssueCommandsService,
    review_reader: ReviewReaderPort,
    pr_lister: PrListerPort,
    review_item_parser: ReviewItemParser,
) -> CliRunner: ...
```

---

---

### 3. `WebhookAdapter` *(optional, future)*

**Drives:** `ReviewPullRequestService`, `ProcessIssueCommandsService`  
**Replaces:** The polling loop entirely — the platform pushes events instead.

**Responsibility:** Receive platform webhook events over HTTP and translate each
event into the appropriate application command.

> This adapter is documented here as a future extension point. The application
> services and ports require no changes to support it — only this adapter needs
> to be written and wired.

---

#### Handled events

| Platform event | Triggers |
|---|---|
| `pull_request.opened` | `ReviewPullRequestCommand` |
| `pull_request.synchronize` (new commit pushed) | `ReviewPullRequestCommand` |
| `issue_comment.created` | `ProcessIssueCommandsCommand` |

---

#### Execution flow (per event)

```
[http] POST /webhook
           Headers: X-Platform-Event, X-Hub-Signature (or platform equivalent)

1.  Verify HMAC signature
    └─ invalid → return HTTP 401

2.  Parse event type from header

3.  case pull_request.opened / pull_request.synchronize:
        [map]  pr_id  = PullRequestId(repository, number)
        [map]  sha    = CommitSha(payload["pull_request"]["head"]["sha"])
        [map]  title  = payload["pull_request"]["title"]
        [cmd]  command = ReviewPullRequestCommand(pr_id, sha, title)
        [cmd]  review_service.execute(command)  (async / background task)

    case issue_comment.created:
        [map]  pr_id = PullRequestId(repository, number)
        [map]  sha   = CommitSha(payload["pull_request"]["head"]["sha"])
        [cmd]  command = ProcessIssueCommandsCommand(pr_id, sha)
        [cmd]  process_commands_service.execute(command)  (async / background task)

    default:
        return HTTP 200  # acknowledge and ignore unknown events

4.  return HTTP 202 Accepted
    # Commands run asynchronously; webhook response must be fast
```

> Application service calls must be dispatched to a background worker or task
> queue. The webhook handler itself must return before the service finishes.

---

---

## Composition Root

The composition root is the **only place** in the entire codebase where concrete
classes are instantiated and wired together. It is not a layer — it is a single
module that knows about all layers so that no other module has to.

```
composition_root.py
    │
    ├─ reads env / config file
    │
    ├─ builds infrastructure adapters:
    │   GitPlatformHttpClient(base_url, token)
    │   ├─ GitChangesetFetcherAdapter(client)
    │   ├─ GitRepositoryContextAdapter(client)
    │   ├─ GitReviewPublisherAdapter(client, reviewer_token, reviewer_username)
    │   ├─ GitReviewReaderAdapter(client)
    │   ├─ GitCommentReaderAdapter(client)
    │   ├─ GitCommentPublisherAdapter(client)
    │   ├─ GitIssueTrackerAdapter(client)
    │   ├─ GitRepoListerAdapter(client, repos_filter)
    │   └─ GitPrListerAdapter(client)
    │
    │   JsonFilePullRequestRepository(state_file_path)
    │   OllamaLlmAdapter(ollama_host, model_name)
    │
    ├─ builds domain services:
    │   ReviewItemParser()
    │   IssueCommandParser()
    │   IssueBodyBuilder()
    │
    ├─ builds application services:
    │   process_commands_service = ProcessIssueCommandsService(
    │       pr_repository, review_reader, comment_reader,
    │       comment_publisher, issue_tracker,
    │       review_item_parser, issue_command_parser, issue_body_builder
    │   )
    │   review_service = ReviewPullRequestService(
    │       pr_repository, changeset_fetcher, repository_context,
    │       llm_review, review_publisher, process_commands_service
    │   )
    │
    └─ builds and starts the inbound adapter:
        PollingDaemon(config, repo_lister, pr_lister, review_service).start()
        # or: CliRunner(review_service, process_commands_service, ...).run(sys.argv)
        # or: WebhookAdapter(review_service, process_commands_service).serve()
```

> Only the composition root does `import` across layers. Application services
> import only ports (interfaces). Adapters import only the port they implement.
> Domain objects import nothing from outside the domain.

---

## What the Presentation Layer Must Never Do

- Contain business logic or domain conditionals.
- Import infrastructure adapters directly — it receives application services
  already wired by the composition root.
- Call ports directly (except `list-items` which is an explicit inspection
  shortcut, not a use-case).
- Persist state or mutate the aggregate — that is always done inside the
  application service.
- Return platform-specific data structures to the application layer.
