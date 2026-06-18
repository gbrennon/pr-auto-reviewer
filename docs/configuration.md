# Configuration

## Environment Variables

All configuration via environment variables. Two ways to set:

1. **Project `.env`** - For manual/dev mode
2. **User config** - `~/.config/pr-auto-reviewer/config` for service mode

## Required Variables

The application uses generic variables for the platform token and reviewer token to support multiple Git hosts (GitHub, Codeberg/Forgejo).

| Variable | Description |
|----------|-------------|
| `PLATFORM_MODE` | Platform to use: `codeberg`, `github`, or `both` |
| `PLATFORM_TOKEN` | Owner account API token (used if mode is `codeberg` or `github`). |
| `REVIEWER_TOKEN` | Reviewer account API token (used if mode is `codeberg` or `github`). |
| `REVIEWER_USERNAME` | Username of the reviewer account (used if mode is `codeberg` or `github`). |
| `OLLAMA_MODEL` | Model name to use for reviews. |

### Multi-Platform Mode (`PLATFORM_MODE=both`)
When reviewing PRs from both platforms simultaneously, you must provide separate tokens for each host:
- **GitHub**: Set `GITHUB_TOKEN`, `GITHUB_REVIEWER_TOKEN`, and `GITHUB_REVIEWER_USERNAME`.
- **Codeberg/Forgejo**: Set `FORGEJO_TOKEN`, `FORGEJO_REVIEWER_TOKEN`, and `FORGEJO_REVIEWER_USERNAME`.

### Single-Platform Fallbacks
If `PLATFORM_MODE` is not `both`, the application will look for:
- **Forgejo/Codeberg**: `FORGEJO_TOKEN`, `FORGEJO_REVIEWER_TOKEN`, `FORGEJO_REVIEWER_USERNAME`.
- **GitHub**: `GITHUB_TOKEN`, `GITHUB_REVIEWER_TOKEN`, `GITHUB_REVIEWER_USERNAME`.

## Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |
| `POLL_INTERVAL` | `60` | Seconds between PR checks |
| `REPO_ROOT` | `.` | Project root directory |

## Generating Tokens

### GitHub
1. Go to **Settings** $\rightarrow$ **Developer settings** $\rightarrow$ **Personal access tokens** $\rightarrow$ **Tokens (classic)**.
2. Create a new token with scopes: `repo` (all), `read:user`, and `user:email`.
3. Copy to `PLATFORM_TOKEN` (or `GITHUB_TOKEN`).

### Codeberg / Forgejo
1. Go to **Settings** $\rightarrow$ **Applications**.
2. Create new token with scopes: `repo`, `read:user`.
3. Copy to `PLATFORM_TOKEN` (or `FORGEJO_TOKEN`).

### Reviewer Tokens
For both platforms, create a separate account for the bot and generate a token with `repo` scope. Copy this to `REVIEWER_TOKEN` (or the platform-specific equivalent) and set `REVIEWER_USERNAME` to the bot's username.

## Example .env

```bash
PLATFORM_MODE=github
PLATFORM_TOKEN=ghp_your_github_token
REVIEWER_TOKEN=ghp_your_reviewer_token
REVIEWER_USERNAME=code-reviewer-bot
OLLAMA_MODEL=code-review
OLLAMA_HOST=http://localhost:11434
POLL_INTERVAL=60
PROMPT_MODE=fragments
USE_STRICT_FRAGMENT_SELECTION=true
```

### Feature flags

- `PROMPT_MODE` (required if you want to change behavior) — Set to `monolithic` or `fragments`. When set, controls which prompt composition approach is used. Example: `PROMPT_MODE=fragments`.
- `USE_STRICT_FRAGMENT_SELECTION` (default: `false`) — When using fragment-based prompts, set to `true` to only include fragments strictly related to files changed in the PR.