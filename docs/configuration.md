# Configuration

## Environment Variables

All configuration via environment variables. Two ways to set:

1. **Project `.env`** - For manual/dev mode
2. **User config** - `~/.config/pr-auto-reviewer/config` for service mode

## Required Variables

| Variable | Description |
|----------|-------------|
| `FORGEJO_TOKEN` | Your account API token. Scopes: `repo`, `read:user` |
| `FORGEJO_HOST` | Platform URL. E.g., `https://codeberg.org` or `http://forgejo:3000` |
| `FORGEJO_REVIEWER_TOKEN` | Different account's token. Scopes: `repo` |
| `FORGEJO_REVIEWER_USERNAME` | Username of reviewer account |
| `OLLAMA_MODEL` | Model name to use for reviews |

## Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama API endpoint |
| `POLL_INTERVAL` | `60` | Seconds between PR checks |
| `REPO_ROOT` | `.` | Project root directory |

## Generating Tokens

### Owner Token
1. Go to platform settings → Applications
2. Create new token with scopes: `repo`, `read:user`
3. Copy to `FORGEJO_TOKEN`

### Reviewer Token
1. Create account (different from owner)
2. Go to platform settings → Applications
3. Create token with scope: `repo`
4. Copy to `FORGEJO_REVIEWER_TOKEN`
5. Set `FORGEJO_REVIEWER_USERNAME` to account name

## Example .env

```bash
FORGEJO_TOKEN=your_owner_token_here
FORGEJO_HOST=https://codeberg.org
FORGEJO_REVIEWER_TOKEN=your_reviewer_token_here
FORGEJO_REVIEWER_USERNAME=code-reviewer
OLLAMA_MODEL=code-review
OLLAMA_HOST=http://localhost:11434
POLL_INTERVAL=60
USE_MONOLITHIC_PROMPT=true
USE_STRICT_FRAGMENT_SELECTION=false
```

### Feature flags

- `PROMPT_MODE` (required if you want to change behavior) — Set to `monolithic` or `fragments`. When set, controls which prompt composition approach is used. Example: `PROMPT_MODE=fragments`.
- `USE_STRICT_FRAGMENT_SELECTION` (default: `false`) — When using fragment-based prompts, set to `true` to only include fragments strictly related to files changed in the PR.