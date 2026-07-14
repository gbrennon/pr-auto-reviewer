# Token Setup

PR Auto Reviewer uses **two tokens per platform** with different permission levels:

| Token | Role | Purpose |
|-------|------|---------|
| **Owner** | Reads data, requests reviewers | Fetch PRs, diff, files, repo tree |
| **Reviewer** | Submits the review | Post review verdict + inline comments |

The reviewer can be the same account as the owner, but must **differ from the PR author** — self-review is blocked by both GitHub and Codeberg.

---

## Environment Variables

| Variable | Platform | Purpose |
|----------|----------|---------|
| `GITHUB_OWNER_TOKEN` | GitHub | Owner token |
| `GITHUB_REVIEWER_TOKEN` | GitHub | Reviewer token |
| `GITHUB_REVIEWER_USERNAME` | GitHub | Reviewer's GitHub username |
| `FORGEJO_OWNER_TOKEN` | Codeberg | Owner token |
| `FORGEJO_REVIEWER_TOKEN` | Codeberg | Reviewer token |
| `FORGEJO_REVIEWER_USERNAME` | Codeberg | Reviewer's Codeberg username |

For single-platform mode (`PLATFORM_MODE=github` or `PLATFORM_MODE=codeberg`), the app falls back to `PLATFORM_TOKEN` / `REVIEWER_TOKEN` / `REVIEWER_USERNAME` if the platform-specific vars are unset.

---

## Auth Header Format

| Platform | Header |
|----------|--------|
| GitHub | `Authorization: Bearer {token}` |
| Codeberg / Forgejo | `Authorization: token {token}` |

Using the wrong prefix causes `401 Unauthorized` even with a valid token.

---

## Platform-Specific Docs

| Doc | Covers |
|-----|--------|
| [GitHub](github.md) | Classic vs fine-grained PAT, permission tables, org resource owner, step-by-step creation, verification curls |
| [Codeberg](codeberg.md) | Forgejo scope system, repo access options (All/Public/Specific), org nuance, step-by-step creation, verification curls |
