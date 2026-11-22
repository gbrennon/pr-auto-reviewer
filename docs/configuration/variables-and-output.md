# Required Variables

The only strictly required variable is `PLATFORM_MODE`
and at least one platform's token set.

| Variable | Description |
|----------|-------------|
| `PLATFORM_MODE` | Platform to use: `codeberg`, `github`, or `both` |
| `LLM_MODEL` | Model name for AI reviews |

### Single-Platform Tokens

Set the token group that matches your `PLATFORM_MODE`:

**GitHub (`PLATFORM_MODE=github`):**

| Variable | Description |
|----------|-------------|
| `GITHUB_MANAGER_TOKEN` | Manager account API token (classic or fine-grained PAT) |
| `GITHUB_REVIEWER_TOKEN` | Bot account token for posting reviews |
| `GITHUB_REVIEWER_USERNAME` | Bot's GitHub username |

**Codeberg / Forgejo (`PLATFORM_MODE=codeberg`):**

| Variable | Description |
|----------|-------------|
| `FORGEJO_MANAGER_TOKEN` | Manager account API token |
| `FORGEJO_REVIEWER_TOKEN` | Bot account token for posting reviews |
| `FORGEJO_REVIEWER_USERNAME` | Bot's Codeberg username |

### Multi-Platform Mode (`PLATFORM_MODE=both`)

When reviewing PRs from both platforms simultaneously, provide
**both** token groups above. The application creates independent
adapters for each host and dispatches reviews to the matching platform.

## Git Host Connection

Variables that control how the application reaches and interacts
with the Git host.

| Variable | Default | Description |
|----------|---------|-------------|
| `GITHUB_API_URL` | `https://api.github.com` | GitHub API base URL |
| `FORGEJO_API_URL` | `https://codeberg.org` | Forgejo API base URL; `/api/v1` is appended |
| `FORGEJO_HOST` | — | Legacy alias for `FORGEJO_API_URL` |
| `LOCAL_CLONE_BASE_DIR` | `~/.cache/pr-auto-reviewer/repos` | Where clones are stored |
| `CLONE_PROTOCOL` | `https` | Protocol for local clones: `https` or `ssh` |

`FORGEJO_API_URL` is normalised automatically: `https://codeberg.org`
becomes `https://codeberg.org/api/v1`.
Set it to a custom Forgejo instance (e.g. `https://git.example.com`)
and the `/api/v1` suffix is added only if missing.

`CLONE_PROTOCOL` selects the clone URL format: `https` uses the HTTPS
resolver (default), `ssh` uses the SSH resolver which produces
`git@host:owner/repo.git` URLs and sets `GIT_SSH_COMMAND` to
`ssh -o BatchMode=yes -o StrictHostKeyChecking=accept-new` on every
`git` subprocess call.

## Review Output

`REVIEW_OUTPUT` controls **where** review results are sent.

| Value | Behaviour |
|-------|-----------|
| `forgejo` (default) | Post review to the PR on Codeberg/Forgejo |
| `github` | Post review to the PR on GitHub |
| `terminal` | Print review to stdout only (no API calls) |
| `file:<path>` | Write review to `<path>` and print to stdout |

The platform value must match the PR's host — sending a `github`
review to a Codeberg PR will fail. `terminal` and `file:` modes
are safe for testing without touching the PR.

`GITHUB_REVIEW_MODE` selects the review type for GitHub PRs:

| Value | Behaviour |
|-------|-----------|
| `formal` (default) | Formal PR review with verdict + inline comments |
| `comment` | Single general comment on the PR |

Codeberg always uses formal reviews (`event: "APPROVED"`, `official: true`).

## Inconclusive Reviews

When a review ends with a *default* outcome — every reported finding is
refuted by source-code verification, leaving an empty approval — the app
does not publish a hollow review. It re-runs with a prompt grounded in
the prior attempts, up to a configurable cap. If the retries remain
inconclusive, the review fails instead of publishing an unverified verdict.

| Variable | Default | Description |
|----------|---------|-------------|
| `REVIEW_MAX_TRIES` | `2` | Max re-run attempts before refusing an inconclusive outcome |
