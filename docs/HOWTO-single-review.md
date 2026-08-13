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
LLM_MODEL=code-review:latest
```

### Codeberg

```ini
PLATFORM_MODE=codeberg
FORGEJO_OWNER_TOKEN=xxx                   # owner token
FORGEJO_REVIEWER_TOKEN=xxx                # reviewer token
FORGEJO_REVIEWER_USERNAME=my-bot          # reviewer username
LLM_MODEL=code-review:latest
```

### Both Platforms

```ini
PLATFORM_MODE=both
GITHUB_OWNER_TOKEN=xxx
GITHUB_REVIEWER_TOKEN=xxx
GITHUB_REVIEWER_USERNAME=my-bot
FORGEJO_OWNER_TOKEN=xxx
FORGEJO_REVIEWER_TOKEN=xxx
FORGEJO_REVIEWER_USERNAME=my-bot
LLM_MODEL=code-review:latest
```

## Options

### `review` command

| Flag | Description |
|------|-------------|
| `--repo`, `-r` | `owner/repo` (required) |
| `--pr`, `-p` | PR number (required) |
| `--force` | Re-review even if already reviewed at this SHA |
| `--verbose`, `-v` | Show debug logs |

### Other Commands

| Command | Description |
|---------|-------------|
| `process-commands --repo owner/repo --pr N [-v]` | Process issue creation commands from PR comments |
| `list-items --repo owner/repo --pr N [-v]` | List parsed review items from latest review |
| `clean` | Reset all reviewed-PR tracking state |
| `bootstrap` | Initialize config and verify tokens |
| `watch-prs [-i INTERVAL] [-r REPO] [--once] [-p PR] [-v]` | Run polling daemon (foreground) |

## Review Modes

Set `GITHUB_REVIEW_MODE` in `.env`:

| Value | Behaviour |
|-------|-----------|
| `formal` (default) | Formal PR review with verdict + inline comments |
| `comment` | General comment on the PR |

> Codeberg formal reviews use `event: "APPROVED"` and `official: true`. Handled automatically.

## Output Modes

Set `REVIEW_OUTPUT` in `.env`:

| Value | Behaviour |
|-------|-----------|
| `forgejo` (default) | Post review to PR on Codeberg/Forgejo |
| `github` | Post review to PR on GitHub |
| `terminal` | Print review to stdout only (no API calls) |
| `file:<path>` | Write review to `<path>` and print to stdout |

Use `terminal` or `file:` for testing without touching the PR.

## Token Setup

See [docs/tokens/](tokens/README.md) for full instructions on creating tokens and setting required permissions.

## Troubleshooting

| Symptom | Cause |
|---------|-------|
| `403 Forbidden` | Token missing write permissions, or reviewer is PR author |
| `401 Unauthorized` | Invalid/expired token or wrong auth header format |
| `Ollama call failed` | Ollama not running or model not pulled |
| `Empty diff` | PR has no changes or clone failed |

### Debug Tips

```bash
# Verbose output
uv run python -m pr_auto_reviewer review -r owner/repo -p N -v

# Test without posting (terminal mode)
REVIEW_OUTPUT=terminal uv run python -m pr_auto_reviewer review -r owner/repo -p N

# Check Ollama
curl http://localhost:11434/api/tags

# View state file
cat ~/.config/pr-auto-reviewer/state.json | python3 -m json.tool

# Check logs (if running as service)
journalctl --user -u pr-auto-reviewer.service -f
```