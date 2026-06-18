# PR Auto Reviewer

AI-powered code review for **GitHub** and **Codeberg/Forgejo** — using local Ollama models.

## Quick Start

```bash
cp .env.example .env   # edit .env with your tokens
uv run pr-auto-reviewer review --repo owner/repo --pr <number>
```

See [How to Run a Single Review](docs/HOWTO-single-review.md) for full instructions.

## Daemon Mode

Poll all repos continuously, reviewing open PRs automatically:

```bash
uv run pr-auto-reviewer watch-prs                  # poll every 60s
uv run pr-auto-reviewer watch-prs -i 120           # poll every 120s
uv run pr-auto-reviewer watch-prs -r owner/repo    # watch a single repo
uv run pr-auto-reviewer watch-prs --once           # run once and exit
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