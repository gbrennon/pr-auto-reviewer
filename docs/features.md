# Features

This document outlines what is currently implemented and what is planned.

## Implemented

### Core Functionality

- **Automatic PR Detection** — Watches all open PRs across configured platforms (Codeberg and/or GitHub)
- **Single Repo Watch** — ``-r owner/repo`` restricts daemon to one repository (no platform prefix supported; same filter applied to both platforms in ``PLATFORM_MODE=both``)
- **Draft PR Skipping** - Skips draft PRs automatically
- **Duplicate Prevention** - Uses SHA-based state to avoid re-reviewing unchanged PRs
- **AI Code Review** - Sends PR diff to Ollama and receives review
- **Review Posting** - Submits formal review (approve/request_changes) with inline diff comments
- **Comment Review** - Non-blocking items posted as single comment on PR (COMMENTED verdict)

### Configuration

- **Environment-based Config** — All settings in ``.env`` or user config; see [Configuration](configuration.md) for the full variable reference
- **Configurable Poll Interval** — Set via ``POLL_INTERVAL`` env var
- **Configurable LLM** — Host and model configurable via ``LLM_HOST`` / ``LLM_MODEL`` env vars

### Operations

- **Bootstrap** — `uv run python -m pr_auto_reviewer bootstrap` sets up repo config
- **Daemon Mode** — `uv run python -m pr_auto_reviewer daemon start|stop|status`
- **Single Review** — `uv run python -m pr_auto_reviewer task --repo <org>/<repo> --pr <N>`
- **Command Processing** — `uv run python -m pr_auto_reviewer process-commands --repo <org>/<repo> --pr <N>`

### Service Management

- **systemd Integration** — `scripts/install-service.sh` installs and enables the daemon
- **Start/Stop/Status** — `systemctl --user` controls the background service


### Code Review Features

- **Verdict System** — AI determines Approved, Changes Requested, or Commented based on findings
- **Structured Domain Model** — Review output uses typed entities (ReviewItem, ReviewSuggestion, ReviewPraise)
- **Severity Awareness** — AI identifies critical, major, minor, and info-level issues
- **Inline Comments** — Per-file, per-line annotations in review body

### GitHub Support

- **Full GitHub API integration** — PR diff, file content, commit fetching
- **Formal reviews** — Approve, request changes, or comment on GitHub PRs
- **Dual-platform** — ``PLATFORM_MODE=both`` reviews PRs on both GitHub and Codeberg simultaneously
- **Per-org token overrides** — ``GITHUB_TOKEN_<org>_OWNER`` for multi-org setups

### Advanced

- **Configurable review output** — ``REVIEW_OUTPUT`` controls terminal-only, file, or platform posting
- **Local clone mode** — ``USE_LOCAL_CLONE`` switches from API to local ``git`` operations; ``CLONE_PROTOCOL`` selects ``https`` (default) or ``ssh``
- **Prompt fragment system** — Language-specific review guidance via composable fragments
- **Compact template** — ``USE_COMPACT_TEMPLATE`` reduces prompt size for smaller models

## Not Implemented (Planned)

- **Platform-Prefix Repo Filter** — ``-r github:owner/repo,codeberg:other/repo`` to scope filters per platform in ``PLATFORM_MODE=both``
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

## Supported Platforms

| Platform | Status |
|----------|--------|
| Codeberg | Tested and working |
| GitHub | Implemented |
| Forgejo | Should work (Codeberg API compatible) |
| Gitea | Should work (Forgejo fork) |
