# Per-Organisation Token Overrides

When a single token needs to review repos across multiple organisations,
override tokens per org:

```
GITHUB_TOKEN_myorg_MANAGER=ghp_xxx
GITHUB_TOKEN_myorg_REVIEWER=ghp_yyy
GITHUB_TOKEN_myorg_REVIEWER_USERNAME=code-reviewer-bot
FORGEJO_TOKEN_myorg_MANAGER=fc_xxx
FORGEJO_TOKEN_myorg_REVIEWER=fc_yyy
FORGEJO_TOKEN_myorg_REVIEWER_USERNAME=code-reviewer-bot
```

The prefix is the platform (`GITHUB` or `FORGEJO`) followed by `_TOKEN_`,
then the organisation name, then the role suffix (`_MANAGER`, `_REVIEWER`,
or `_REVIEWER_USERNAME`). The standard (non-org) token `GITHUB_MANAGER_TOKEN`
is always available as the default.

## Generating Tokens

For comprehensive token setup guides including scopes, permissions,
and platform-specific details, see `docs/tokens/ <tokens/>`_.

### GitHub

**Classic PAT:**
1. Go to **Settings** → **Developer settings** → **Personal access tokens** →
   **Tokens (classic)**.
2. Create a new token with scopes: `repo` (all) and `read:user`.
3. Copy to `GITHUB_MANAGER_TOKEN`.

**Fine-grained PAT:** Requires explicit org/repo assignment, even for public
repos. If the org does not appear under "Resource owner", use a classic PAT.

1. Go to **Settings** → **Developer settings** → **Personal access tokens** →
   **Fine-grained tokens**.
2. Set **Resource owner** to the target org.
3. Grant repository access: **Selected repositories** → choose the repos.
4. Set permissions:
   - `Metadata`: **Read** (auto-selected)
   - `Pull requests`: **Write**
   - `Contents`: **Write** (needed to read PR diff)
   - `Administration`: **Read** (needed for branch info)
5. Copy to `GITHUB_MANAGER_TOKEN`.

### Codeberg / Forgejo

1. Go to **Settings** → **Applications**.
2. Create new token with scopes: `repo`, `read:user`.
3. Copy to `FORGEJO_MANAGER_TOKEN`.

### Reviewer Tokens

For both platforms, create a separate account for the bot and generate a token
with `repo` scope. Copy it to `FORGEJO_REVIEWER_TOKEN` or
`GITHUB_REVIEWER_TOKEN` and set the corresponding `_USERNAME` to the bot.

## Example .env

```bash
# --- Single-platform: GitHub ---
PLATFORM_MODE=github
GITHUB_MANAGER_TOKEN=ghp_your_github_token
GITHUB_REVIEWER_TOKEN=ghp_your_reviewer_token
GITHUB_REVIEWER_USERNAME=code-reviewer-bot

# --- Single-platform: Codeberg ---
# PLATFORM_MODE=codeberg
# FORGEJO_MANAGER_TOKEN=fc_your_codeberg_token
# FORGEJO_REVIEWER_TOKEN=fc_your_reviewer_token
# FORGEJO_REVIEWER_USERNAME=code-reviewer-bot

# --- Multi-platform ---
# PLATFORM_MODE=both
# GITHUB_MANAGER_TOKEN=...
# GITHUB_REVIEWER_TOKEN=...
# GITHUB_REVIEWER_USERNAME=...
# FORGEJO_MANAGER_TOKEN=...
# FORGEJO_REVIEWER_TOKEN=...
# FORGEJO_REVIEWER_USERNAME=...

# --- Review output ---
REVIEW_OUTPUT=terminal

# --- LLM ---
LLM_MODEL=code-review
LLM_HOST=http://localhost:11434

# --- Daemon ---
POLL_INTERVAL=60
```

### Feature Flags

- `USE_STRICT_FRAGMENT_SELECTION` (default: `false`) — Set to `true` to only
  include fragments related to files changed in the PR.
- `USE_COMPACT_TEMPLATE` (default: `false`) — Use the shorter prompt template
  for smaller models.
