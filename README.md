# PR Auto Reviewer

AI-powered code review for **GitHub** and **Codeberg/Forgejo** — using local Ollama models.

## Quick Start

```bash
cp .env.example .env   # edit .env with your tokens
uv run pr-auto-reviewer review --repo owner/repo --pr <number>
```

See [How to Run a Single Review](docs/HOWTO-single-review.md) for full instructions.

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