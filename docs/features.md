# Features

This document outlines what is currently implemented and what is planned.

## Implemented

### Core Functionality

- **Automatic PR Detection** — Watches all open PRs across configured platforms (Codeberg and/or GitHub)
- **Single Repo Watch** — `-r owner/repo` restricts daemon to one repository. Supports platform prefix: `-r github:owner/repo` or `-r codeberg:owner/repo` to scope filter per platform in `PLATFORM_MODE=both`
- **Draft PR Skipping** — Skips draft PRs automatically
- **Duplicate Prevention** — Uses SHA-based state to avoid re-reviewing unchanged PRs
- **AI Code Review** — Sends PR diff to Ollama and receives review
- **Review Posting** — Submits formal review (approve/request_changes) with inline diff comments. Forgejo splits non-blocking items (MINOR/INFO) into a separate comment; GitHub keeps all items in the formal review.
- **Comment Review** — COMMENTED verdict path: all items posted as a single comment on the PR (no formal review)
- **Local Git Clone Diff Fetching** — Uses local git clones to compute diffs and read file contents, avoiding API rate limits and providing full file context
- **Multi-Platform Support** — Single application instance polls PRs on both GitHub and Codeberg/Forgejo; each PR is reviewed on its originating platform (determined by platform prefix or platform mode)

### Configuration

- **Environment-based Config** — All settings in `.env` or user config; see [Configuration](configuration.md) for the full variable reference
- **Configurable Poll Interval** — Set via `POLL_INTERVAL` env var
- **Configurable LLM** — Host and model configurable via `LLM_HOST` / `LLM_MODEL` env vars
- **Configurable Clone Protocol** — HTTPS or SSH for local git clones via `CLONE_PROTOCOL`
- **Per-Organization Token Overrides** — Different tokens per org for multi-org setups

### Operations

- **Bootstrap** — `uv run python -m pr_auto_reviewer bootstrap` sets up repo config
- **Daemon Mode** — `uv run python -m pr_auto_reviewer start|stop|status|restart|logs`
- **Polling Daemon** — `uv run python -m pr_auto_reviewer watch-prs [-i INTERVAL] [-r REPO] [--once] [-p PR] [-v]`
- **Single Review** — `uv run python -m pr_auto_reviewer review --repo <org>/<repo> --pr <N> [--force] [-v]`
- **Command Processing** — `uv run python -m pr_auto_reviewer process-commands --repo <org>/<repo> --pr <N> [-v]`
- **List Review Items** — `uv run python -m pr_auto_reviewer list-items --repo <org>/<repo> --pr <N> [-v]`
- **Clean State** — `uv run python -m pr_auto_reviewer clean` resets reviewed PR tracking

### Service Management

- **systemd Integration** — `scripts/install-service.sh` installs and enables the daemon
- **Start/Stop/Status** — `systemctl --user` controls the background service
- **Logs** — `journalctl --user -u pr-auto-reviewer.service -f`

### Code Review Features

- **Verdict System** — AI determines Approved, Changes Requested, or Commented based on findings
- **Structured Domain Model** — Review output uses typed entities (ReviewItem, ReviewSuggestion, ReviewPraise)
- **Severity Awareness** — AI identifies critical, major, minor, and info-level issues
- **Blocking vs Non-Blocking** — CRITICAL and MAJOR severity items block merge; SECURITY category always blocks regardless of severity
- **Inline Comments** — Per-file, per-line annotations in review body
- **Deterministic Findings** — Automatically detects and flags noisy INFO-level logging in diffs
- **Unresolved Blocker Tracking** — Persists blocking items across reviews; overrides verdict to CHANGES_REQUESTED if blockers remain
- **Item Numbering** — Items numbered sequentially across reviews to avoid duplicate numbers
- **Praise & Suggestions** — Separate praise items and code suggestions from issues

### GitHub Support

- **Full GitHub API integration** — PR diff, file content, commit fetching
- **Formal reviews** — Approve, request changes, or comment on GitHub PRs
- **Multi-platform polling** — `PLATFORM_MODE=both` polls PRs on both GitHub and Codeberg; each PR reviewed on its platform
- **Per-org token overrides** — `GITHUB_TOKEN_<org>_OWNER` for multi-org setups
- **Review Mode** — `GITHUB_REVIEW_MODE=formal|comment` controls review type

### Codeberg/Forgejo Support

- **Full Forgejo/Codeberg API integration** — PR diff, file content, commit fetching
- **Formal reviews** — Uses `event: "APPROVED"` and `official: true` (Forgejo-specific)
- **Inline comments** — Uses Forgejo's `old_position`/`new_position` format
- **Non-blocking item split** — MINOR/INFO items posted as separate PR comment
- **Per-org token overrides** — `FORGEJO_TOKEN_<org>_OWNER` for multi-org setups

### Advanced Review Features

- **Multi-Phase Review Orchestrator** — Runs review in multiple phases (e.g., security, architecture, style) with findings passed between phases
- **Agent System** — Specialized agents for different review aspects: AdvisorAgent (advice), ArchitectAgent (architecture), EngineerAgent (implementation), ExplorerAgent (code exploration), ManagerAgent (orchestration), ReviewerAgent (review), with shared Conversation and ConversationMessage infrastructure
- **Agent Conversation Service** — Multi-turn agentic conversation with tool access (read_file, search_codebase, list_directory, run_git, get_changed_files)
- **Finding Verification** — Validates LLM findings against actual source code before publishing
- **Finding Aggregation** — Merges findings from multiple phases, deduplicates
- **Retry Orchestration** — Automatic retry on LLM errors, token exhaustion, unparseable responses
- **Feedback Loops** — Re-runs review with feedback when zero items found
- **Prompt Fragment System** — Language-specific review guidance via composable fragments with priority-based selection
- **Token Budget Management** — Greedy fragment selection to fit within token limits
- **Strict Fragment Selection** — Optional heuristic filtering to include only fragments relevant to changed files (`USE_STRICT_FRAGMENT_SELECTION`)
- **Compact Template** — `USE_COMPACT_TEMPLATE` reduces prompt size for smaller models
- **Max Token/Char Limits** — Configurable limits on prompt size, file chars, file count, structure lines

### LLM Integration

- **Ollama Local Inference** — Runs against local Ollama instance
- **System/User Prompt Split** — First fragment (reviewer-system-prompt) sent as Ollama `system` parameter
- **Streaming/Non-Streaming** — Non-streaming by default for simpler parsing
- **Response Parsing** — Robust JSON parsing with brace-matching and Markdown fallback
- **Response Normalization** — Handles malformed LLM output, retries with correction prompts
- **Max Retries** — Configurable via `LLM_MAX_RETRIES` (default 5)
- **Timeout** — Configurable via `OLLAMA_TIMEOUT` (default 120s)

### Security & Token Management

- **Preflight Token Verification** — Verifies both owner and reviewer tokens have required scopes before each review
- **Token Verification Caching** — Caches verified tokens to `~/.config/pr-auto-reviewer/verified-tokens.json`
- **Rate Limit Tracking** — Tracks `x-ratelimit-*` headers, persists to disk, backs off before exhaustion
- **Auth Header Format** — `Bearer` for GitHub, `token` for Forgejo/Codeberg
- **Separate Owner/Reviewer Tokens** — Different tokens for reading vs writing

### Testing & Observability

- **HTTP Request Counter** — Logs summary of HTTP requests per review
- **Conversation Logging** — Optional logging of full LLM conversations to disk
- **Prompt Dumping** — Dumps prompts to `/tmp/ollama-prompt-try*.txt` for debugging
- **Integration Tests** — Real API calls against test fixtures (no mocks for integration tests)
- **Unit Tests** — AAA pattern with mocks for unit tests

## Not Implemented (Planned)

- **Platform-Prefix Repo Filter** — `-r github:owner/repo,codeberg:other/repo` to scope filters per platform in `PLATFORM_MODE=both`
- **Per-Repo Config** — Different settings per repository
- **Review History** — Store and query past reviews
- **Stats/Dashboard** — Track review patterns
- **Custom Prompts** — User-defined review instructions
- **Multiple Models** — Choose different models per repo or PR type
- **PR Size Limits** — Skip or warn on large PRs
- **Webhook Support** — Event-driven instead of polling
- **Docker Container** — Containerized deployment
- **Health Checks** — HTTP endpoint for monitoring
- **Caching** — Cache reviews for unchanged files
- **Parallel Processing** — Review multiple PRs simultaneously
- **GitLab Support** — GitLab API integration

## Supported Platforms

| Platform | Status |
|----------|--------|
| Codeberg | Tested and working |
| GitHub | Tested and working |
| Forgejo | Should work (Codeberg API compatible) |
| Gitea | Should work (Forgejo fork) |

## Architecture Notes

- **Hexagonal Architecture** — Domain, Application, Infrastructure, Presentation layers
- **Ports & Adapters** — All external dependencies behind Protocol-based ports
- **CQRS** — Separate command and query models
- **Domain Events** — In-memory event bus for cross-cutting concerns
- **Frozen Value Objects** — All domain value objects are immutable (`frozen=True`)
- **DI Container** — Centralized wiring in `CompositionRoot` / `Container`