# PR Auto Reviewer

AI-powered code review for **GitHub** and **Codeberg/Forgejo** — using local Ollama models.

## Quick Start

```bash
cp .env.example .env   # edit .env with your tokens
```

### Single Review

```bash
# GitHub
PLATFORM_MODE=github uv run python -m pr_auto_reviewer review --repo owner/repo --pr 42

# Codeberg
PLATFORM_MODE=codeberg uv run python -m pr_auto_reviewer review --repo owner/repo --pr 42

# Via Make (uses PLATFORM_MODE from .env)
make review REPO=owner/repo PR=42
```

### Daemon Mode

Poll all repos the token can access on **both** GitHub and Codeberg, reviewing open PRs automatically.
Set `PLATFORM_MODE` in `.env` (`github`, `codeberg`, or `both`).

```bash
# Via uv
uv run python -m pr_auto_reviewer watch-prs                  # all repos, every 60s
uv run python -m pr_auto_reviewer watch-prs -r owner/repo    # single repo, every 60s
uv run python -m pr_auto_reviewer watch-prs --once           # one cycle and exit (all repos)
uv run python -m pr_auto_reviewer watch-prs --once -r owner/repo  # one cycle, single repo

# Via Make
make daemon                                         # continuous polling
make daemon-once                                    # one cycle and exit
make watch REPO=owner/repo                          # one cycle, single repo
```

> **Note:** ``-r`` takes a plain ``owner/repo`` string — no platform prefix. In ``PLATFORM_MODE=both``
> mode, the same filter is applied to both platforms. Use ``REPOS_FILTER`` in ``.env`` as an
> alternative to the CLI flag.

Missing or invalid tokens are **logged and skipped** — the daemon never stops on auth errors.

### Install (systemd)

```bash
make install   # installs and enables the systemd service
```

Control the service with `systemctl --user start|stop|status pr-auto-reviewer.service`
or the CLI: `pr-auto-reviewer start|stop|status|logs|restart`.

## Docs

| Doc | Topic |
|-----|-------|
| [How to Run](docs/HOWTO-single-review.md) | Single PR review walkthrough |
| [Configuration](docs/configuration.md) | All env vars |
| [Requirements](docs/requirements.md) | Prerequisites & tokens |
| [Makefile](Makefile) | Available commands (`make help`) |
| [Troubleshooting](docs/troubleshooting.md) | Common problems |
| [Testing](docs/HOWTO-test.md) | Running tests |
| [Features](docs/features.md) | What's implemented |
| [Architecture](docs/structure.md) | Codebase structure |
| [Review Flow](docs/review-flow-architecture.md) | Detailed flow |
| [Token Setup](docs/tokens/README.md) | Token types, permissions, verification |
