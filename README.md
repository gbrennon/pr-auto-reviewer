# PR Auto Reviewer

AI-powered code review for **GitHub** and **Codeberg/Forgejo** — using local Ollama models.

## Quick Start

```bash
cp .env.example .env   # edit .env with your tokens
```

### Single Review

```bash
# GitHub
PLATFORM_MODE=github uv run pr-auto-reviewer review --repo owner/repo --pr 42

# Codeberg
PLATFORM_MODE=codeberg uv run pr-auto-reviewer review --repo owner/repo --pr 42

# Via Make (uses PLATFORM_MODE from .env)
make review REPO=owner/repo PR=42
```

### Daemon Mode

Poll all repos the token can access, reviewing open PRs automatically.
Set `PLATFORM_MODE` in `.env` first.

```bash
uv run pr-auto-reviewer watch-prs                  # all repos, every 60s
uv run pr-auto-reviewer watch-prs -r owner/repo    # single repo
uv run pr-auto-reviewer watch-prs --once           # one cycle and exit
uv run pr-auto-reviewer watch-prs -i 120           # poll every 120s
```

## Install (systemd)

```bash
make install            # install and configure systemd service
make start              # start the daemon
make stop               # stop the daemon
make status             # show service status
make logs               # view service logs (follow)
make restart            # restart the service
```

See [Scripts & Makefile](docs/scripts.md) for all commands.

## Docs

| Doc | Topic |
|-----|-------|
| [How to Run](docs/HOWTO-single-review.md) | Single PR review walkthrough |
| [Configuration](docs/configuration.md) | All env vars |
| [Requirements](docs/requirements.md) | Prerequisites & tokens |
| [Scripts & Makefile](docs/scripts.md) | Available commands |
| [Troubleshooting](docs/troubleshooting.md) | Common problems |
| [Testing](docs/HOWTO-test.md) | Running tests |
| [Features](docs/features.md) | What's implemented |
| [Architecture](docs/structure.md) | Codebase structure |
| [Review Flow](docs/review-flow-architecture.md) | Detailed flow |