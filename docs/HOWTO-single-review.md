# How to Run a Single PR Review

One-off review against a pull request on **GitHub** or **Codeberg**.

## Quick Start

```bash
cp .env.example .env   # edit .env with your tokens
uv run pr-auto-reviewer review --repo owner/repo --pr <number>
```

## Environment

The application loads settings from `.env`. See [Configuration](configuration.md).

### GitHub

```ini
PLATFORM_MODE=github
GITHUB_TOKEN=ghp_xxx                    # your token
GITHUB_REVIEWER_TOKEN=ghp_xxx           # bot token (repo scope)
GITHUB_REVIEWER_USERNAME=my-bot         # bot username
OLLAMA_MODEL=code-review:latest
```

### Codeberg

```ini
PLATFORM_MODE=codeberg
FORGEJO_TOKEN=xxx                       # your token
FORGEJO_REVIEWER_TOKEN=xxx              # bot token
FORGEJO_REVIEWER_USERNAME=my-bot        # bot username
OLLAMA_MODEL=code-review:latest
```

## Options

| Flag | Description |
|------|-------------|
| `--repo`, `-r` | `owner/repo` (required) |
| `--pr`, `-p` | PR number (required) |
| `--force` | Re-review even if already reviewed |
| `--verbose`, `-v` | Show debug logs |

## Review Modes

Set `GITHUB_REVIEW_MODE` in `.env`:

| Value | Behaviour |
|-------|-----------|
| `formal` (default) | Formal PR review with verdict + inline comments |
| `comment` | General comment on the PR |

> Codeberg formal reviews use `event: "APPROVED"` and `official: true`. Handled automatically.

## Token Scopes

| Platform | Scopes needed |
|----------|---------------|
| GitHub | `repo` |
| Codeberg | `repo`, `read:user` |

The reviewer account must differ from the PR author. See [Requirements](requirements.md).

## Troubleshooting

| Symptom | Cause |
|---------|-------|
| `403 Forbidden` | Token missing `repo` scope, or reviewer is PR author |
| `401 Unauthorized` | Invalid/expired token |
| `Ollama call failed` | Ollama not running or model not pulled |
