# How to Run a Single PR Review

One-off review against a pull request on **GitHub** or **Codeberg**.

## Quick Start

```bash
cp .env.example .env   # edit .env with your tokens
uv run python -m pr_auto_reviewer review --repo owner/repo --pr <number>
```

## Environment

The application loads settings from `.env`. See [Configuration](configuration.md).

### GitHub

```ini
PLATFORM_MODE=github
GITHUB_OWNER_TOKEN=github_pat_xxx         # owner token
GITHUB_REVIEWER_TOKEN=github_pat_xxx      # reviewer token
GITHUB_REVIEWER_USERNAME=my-bot           # reviewer username
OLLAMA_MODEL=code-review:latest
```

### Codeberg

```ini
PLATFORM_MODE=codeberg
FORGEJO_OWNER_TOKEN=xxx                   # owner token
FORGEJO_REVIEWER_TOKEN=xxx                # reviewer token
FORGEJO_REVIEWER_USERNAME=my-bot          # reviewer username
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

## Token Setup

See [docs/tokens/](tokens/README.md) for full instructions on creating tokens and setting required permissions.

## Troubleshooting

| Symptom | Cause |
|---------|-------|
| `403 Forbidden` | Token missing write permissions, or reviewer is PR author |
| `401 Unauthorized` | Invalid/expired token or wrong auth header format |
| `Ollama call failed` | Ollama not running or model not pulled |
