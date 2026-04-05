# Features

This document outlines what is currently implemented and what is planned.

## Implemented

### Core Functionality

- **Automatic PR Detection** - Watches all user's Codeberg repos for open PRs
- **Single Repo Watch** - Can watch specific repo with `-r owner/repo`
- **Draft PR Skipping** - Skips draft PRs automatically
- **Duplicate Prevention** - Uses SHA-based state to avoid re-reviewing unchanged PRs
- **AI Code Review** - Sends PR diff to Ollama and receives review
- **Review Posting** - Posts formatted review comment to Codeberg PR
- **Formal Review** - Also submits a formal approve/request_changes review

### Configuration

- **Environment-based Config** - All settings in `.env` file
- **Hot Reload** - Changes to `.env` detected within ~10 seconds
- **Manual Reload** - `reload.sh` triggers immediate config reload
- **Configurable Poll Interval** - Set via `POLL_INTERVAL` env var
- **Configurable Ollama** - Host and model configurable via env vars

### Operations

- **Bootstrap** - Single entry point (`bootstrap.sh`) that handles everything
- **Daemon Mode** - Runs continuously in background
- **Single Cycle** - Run once for testing (`--once`)
- **Locking** - Prevents multiple instances from running
- **PID Tracking** - Tracks running process for clean shutdown

### Service Management

- **Autostart System** - Simple service manager for background processes
- **Start/Stop/Status** - Control running services
- **Status Check** - View which services are running

### Code Review Features

- **Verdict System** - AI determines Approved or Changes Requested
- **Structured Output** - Review includes Issues, Suggestions, Praise, Summary
- **Severity Awareness** - AI identifies critical vs minor issues

## Not Implemented (Planned)

### GitHub Support

- GitHub PAT integration not tested
- GitHub API calls not implemented
- Dual platform support planned but not validated

### Advanced Features

- **Webhook Support** - Currently polling-based; webhooks would be faster
- **Per-Repo Config** - Different settings per repository
- **Review History** - Store and query past reviews
- **Stats/Dashboard** - Track review patterns
- **Custom Prompts** - User-defined review instructions
- **Multiple Models** - Choose different models per repo or PR type
- **PR Size Limits** - Skip or warn on large PRs

### Infrastructure

- **Systemd Unit Files** - For native Linux service management
- **Docker Container** - Containerized deployment
- **Health Checks** - HTTP endpoint for monitoring

### AI Improvements

- **Caching** - Cache reviews for unchanged files
- **Parallel Processing** - Review multiple PRs simultaneously
- **Token Budget** - Truncate diffs to stay within model limits

## Supported Platforms

| Platform | Status |
|----------|--------|
| Codeberg | Tested and working |
| GitHub | Not implemented |
| Forgejo | Should work (Codeberg API compatible) |
| Gitea | Should work (Forgejo fork) |
