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

Poll all repos the token can access on **both** GitHub and Codeberg, reviewing open PRs automatically.
Set `PLATFORM_MODE` in `.env` (`github`, `codeberg`, or `both`).

```bash
# Via uv
uv run pr-auto-reviewer watch-prs                  # all repos, every 60s
uv run pr-auto-reviewer watch-prs -r owner/repo    # single repo
uv run pr-auto-reviewer watch-prs --once           # one cycle and exit

# Via Make
make daemon                                         # continuous polling
make daemon-once                                    # one cycle and exit
make watch REPO=owner/repo                          # watch single repo once
```

Missing or invalid tokens are **logged and skipped** — the daemon never stops on auth errors.

### Install (systemd)

Creates shell aliases (`pr-reviewer start|stop|status|logs|restart`) for controlling
the systemd service.  Supported shells: **fish**, **zsh**, **bash**.

```bash
make install-aliases   # write aliases to your shell config
```

See [Install](docs/HOWTO-install.md) for the full systemd setup.

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
| [Token Setup](docs/tokens/README.md) | Token types, permissions, verification |
