# Configuration

All configuration via environment variables, loaded from three sources
(lower number = higher priority):

1. **Shell environment** — ``make`` targets and direct exports
2. **Project ``.env``** — repo root for dev/manual mode
3. **User config** —
   ``~/.config/pr-auto-reviewer/config`` for production/service mode

Application detects ``ENV`` to choose the load path.
Set ``ENV=production`` to use the user config file;
omit or set ``ENV=development`` to use the project ``.env``.

## Required Variables

The only strictly required variable is ``PLATFORM_MODE``
and at least one platform's token set.

| Variable | Description |
|----------|-------------|
| ``PLATFORM_MODE`` | Platform to use: ``codeberg``, ``github``, or ``both`` |
| ``LLM_MODEL`` | Model name for AI reviews (falls back to ``OLLAMA_MODEL``) |

### Single-Platform Tokens

Set the token group that matches your ``PLATFORM_MODE``:

**GitHub (**``PLATFORM_MODE=github``**):**

| Variable | Description |
|----------|-------------|
| ``GITHUB_OWNER_TOKEN`` | Owner account API token (classic or fine-grained PAT) |
| ``GITHUB_REVIEWER_TOKEN`` | Bot account token for posting reviews |
| ``GITHUB_REVIEWER_USERNAME`` | Bot's GitHub username |

**Codeberg / Forgejo (**``PLATFORM_MODE=codeberg``**):**

| Variable | Description |
|----------|-------------|
| ``FORGEJO_OWNER_TOKEN`` | Owner account API token |
| ``FORGEJO_REVIEWER_TOKEN`` | Bot account token for posting reviews |
| ``FORGEJO_REVIEWER_USERNAME`` | Bot's Codeberg username |

### Multi-Platform Mode (``PLATFORM_MODE=both``)

When reviewing PRs from both platforms simultaneously, provide
**both** token groups above.  The application creates independent
adapters for each host and dispatches reviews to the matching platform.

## Git Host Connection

Variables that control how the application reaches and interacts
with the Git host.

| Variable | Default | Description |
|----------|---------|-------------|
| ``GITHUB_API_URL`` | ``https://api.github.com`` | GitHub API base URL (set for Enterprise) |
| ``FORGEJO_API_URL`` | ``https://codeberg.org`` | Forgejo/Codeberg API base URL (``/api/v1`` appended automatically) |
| ``FORGEJO_HOST`` | — | Legacy alias for ``FORGEJO_API_URL`` |
| ``USE_LOCAL_CLONE`` | ``false`` | Clone repos locally instead of fetching via API |
| ``LOCAL_CLONE_BASE_DIR`` | ``~/.cache/pr-auto-reviewer/repos`` | Where clones are stored |
| ``CLONE_PROTOCOL`` | ``https`` | Protocol for local clones: ``https`` or ``ssh`` |

``FORGEJO_API_URL`` is normalised automatically: ``https://codeberg.org``
becomes ``https://codeberg.org/api/v1``.
Set it to a custom Forgejo instance (e.g. ``https://git.example.com``)
and the ``/api/v1`` suffix is added only if missing.
``USE_LOCAL_CLONE`` switches from API-based diff fetching to local ``git``
operations.  Useful when API rate limits are tight or the host has no
diff endpoint.  ``CLONE_PROTOCOL`` selects the clone URL format: ``https``
uses the HTTPS resolver (default), ``ssh`` uses the SSH resolver which
produces ``git@host:owner/repo.git`` URLs and sets ``GIT_SSH_COMMAND``
to ``ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new`` on every
``git`` subprocess call.

## Review Output

``REVIEW_OUTPUT`` controls **where** review results are sent.

| Value | Behaviour |
|-------|-----------|
| ``forgejo`` (default) | Post review to the PR on Codeberg/Forgejo |
| ``github`` | Post review to the PR on GitHub |
| ``terminal`` | Print review to stdout only (no API calls) |
| ``file:<path>`` | Write review to ``<path>`` and print to stdout |

The platform value must match the PR's host — sending a ``github``
review to a Codeberg PR will fail.  ``terminal`` and ``file:`` modes
are safe for testing without touching the PR.

``GITHUB_REVIEW_MODE`` selects the review type for GitHub PRs:

| Value | Behaviour |
|-------|-----------|
| ``formal`` (default) | Formal PR review with verdict + inline comments |
| ``comment`` | Single general comment on the PR |

Codeberg always uses formal reviews (``event: "APPROVED"``,
``official: true``).

## LLM Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| ``LLM_HOST`` | ``http://localhost:11434`` | LLM API endpoint (preferred; falls back to ``OLLAMA_HOST``) |
| ``OLLAMA_HOST`` | ``http://localhost:11434`` | Legacy name for ``LLM_HOST`` |
| ``LLM_MODEL`` | — | Model name (preferred; falls back to ``OLLAMA_MODEL``) |
| ``OLLAMA_MODEL`` | — | Legacy name for ``LLM_MODEL`` |
| ``OLLAMA_TIMEOUT`` | ``120`` | Seconds before a generation request times out |
| ``LLM_MAX_RETRIES`` | ``5`` | Max retries on transient LLM errors |

## Daemon Settings

| Variable | Default | Description |
|----------|---------|-------------|
| ``POLL_INTERVAL`` | ``60`` | Seconds between PR checks in watch mode |
| ``RUN_ONCE`` | ``false`` | Run one check cycle and exit |
| ``REPOS_FILTER`` | — | Comma-separated repo names to watch (empty = all) |
| ``FORCE_PR`` | — | PR number to re-review regardless of state |
| ``DEBUG`` | ``false`` | Enable debug logging (``1``, ``true``, or ``yes``) |
| ``ENV`` | ``development`` | Set to ``production`` to load from user config |

## Prompt Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| ``MAX_PROMPT_TOKENS`` | ``9999`` | Prompt token budget ceiling |
| ``MAX_FILE_CHARS`` | ``3000`` | Max characters per source file in prompt |
| ``MAX_FILES`` | ``10`` | Max files included in the review prompt |
| ``MAX_STRUCTURE_LINES`` | ``100`` | Max lines of repo structure in prompt |
| ``USE_COMPACT_TEMPLATE`` | ``false`` | Use the shorter prompt template |
| ``USE_STRICT_FRAGMENT_SELECTION`` | ``false`` | Only include fragments for changed files |

## Per-Organisation Token Overrides

When a single token needs to review repos across multiple organisations,
override tokens per org:

```
GITHUB_TOKEN_myorg_OWNER=ghp_xxx
GITHUB_TOKEN_myorg_REVIEWER=ghp_yyy
GITHUB_TOKEN_myorg_REVIEWER_USERNAME=code-reviewer-bot
FORGEJO_TOKEN_myorg_OWNER=fc_xxx
FORGEJO_TOKEN_myorg_REVIEWER=fc_yyy
FORGEJO_TOKEN_myorg_REVIEWER_USERNAME=code-reviewer-bot
```

The prefix is the platform (``GITHUB`` or ``FORGEJO``) followed by ``_TOKEN_``,
then the organisation name, then the role suffix (``_OWNER``, ``_REVIEWER``,
or ``_REVIEWER_USERNAME``).  The standard (non-org) token ``GITHUB_OWNER_TOKEN``
is always available as the default.

## Generating Tokens

### GitHub

**Classic PAT:**
1. Go to **Settings** → **Developer settings** → **Personal access tokens** → **Tokens (classic)** (https://github.com/settings/tokens).
2. Create a new token with scopes: ``repo`` (all) and ``read:user``.
3. Copy to ``GITHUB_OWNER_TOKEN``.

**Fine-grained PAT:** Requires explicit org/repo assignment — even for **public** repos. If the org doesn't appear under "Resource owner", use a classic PAT instead.

1. Go to **Settings** → **Developer settings** → **Personal access tokens** → **Fine-grained tokens** (https://github.com/settings/tokens?type=beta).
2. Set **Resource owner** to the target org.
3. Grant repository access: **Selected repositories** → choose the repos.
4. Set permissions:
   - ``Metadata``: **Read** (auto-selected)
   - ``Pull requests``: **Write**
   - ``Contents``: **Write** (needed to read PR diff)
   - ``Administration``: **Read** (needed for branch info)
5. Copy to ``GITHUB_OWNER_TOKEN``.

### Codeberg / Forgejo
1. Go to **Settings** → **Applications**.
2. Create new token with scopes: ``repo``, ``read:user``.
3. Copy to ``FORGEJO_OWNER_TOKEN``.

### Reviewer Tokens
For both platforms, create a separate account for the bot and generate a token with ``repo`` scope. Copy this to ``FORGEJO_REVIEWER_TOKEN`` / ``GITHUB_REVIEWER_TOKEN`` and set the corresponding ``_USERNAME`` to the bot's username.

## Example .env

```bash
PLATFORM_MODE=github
GITHUB_OWNER_TOKEN=ghp_your_github_token
GITHUB_REVIEWER_TOKEN=ghp_your_reviewer_token
GITHUB_REVIEWER_USERNAME=code-reviewer-bot
LLM_MODEL=code-review
LLM_HOST=http://localhost:11434
POLL_INTERVAL=60
USE_STRICT_FRAGMENT_SELECTION=true
```

### Feature Flags

- ``USE_STRICT_FRAGMENT_SELECTION`` (default: ``false``) — Set to ``true`` to only include fragments strictly related to files changed in the PR.
- ``USE_LOCAL_CLONE`` (default: ``false``) — Clone repos locally and use ``git`` instead of API fetches.