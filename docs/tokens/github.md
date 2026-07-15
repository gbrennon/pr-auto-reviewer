# GitHub Token Setup

---

## Every HTTP Call This App Makes

| Method | Endpoint | Token | Required Permission |
|--------|----------|-------|---------------------|
| `GET` | `/user` | Owner + Reviewer | No specific permission — validates token is not expired |
| `POST` | `/repos/{o}/{r}/pulls/{n}/requested_reviewers` | Owner + Reviewer | **Pull requests: Write** — empty reviewers list probes write access |
| `GET` | `/repos/{o}/{r}/pulls/{n}` | Owner | **Pull requests: Read** — fetches PR metadata |
| `GET` | `/repos/{o}/{r}/pulls/{n}.diff` | Owner | **Pull requests: Read** — fetches the unified diff |
| `GET` | `/repos/{o}/{r}/pulls/{n}/commits` | Owner | **Pull requests: Read** — fetches commit messages |
| `GET` | `/repos/{o}/{r}/contents/{path}?ref={sha}` | Owner | **Contents: Read** — fetches file contents at a commit |
| `GET` | `/repos/{o}/{r}/git/trees/{branch}?recursive=1` | Owner | **Contents: Read** — lists the repository file tree |
| `GET` | `/repos/{o}/{r}/contents/{filename}` | Owner | **Contents: Read** — fetches conventions files |
| `POST` | `/repos/{o}/{r}/pulls/{n}/requested_reviewers` | Owner | **Pull requests: Write** — requests the bot as reviewer |
| `POST` | `/repos/{o}/{r}/pulls/{n}/reviews` | Reviewer | **Pull requests: Write** — submits the formal review |
| `POST` | `/repos/{o}/{r}/issues/{n}/comments` | Reviewer | **Issues: Write** — posts a comment on the PR |
| `GET` | `/repos/{o}/{r}/issues/{n}/comments` | Owner | **Issues: Read** — reads existing comments |


---

## Token Types

| Type | When to use |
|------|-------------|
| **Classic PAT** | Simple setup, single user, no org approval needed. Works across all repos the user can access. Use `repo` scope. |
| **Fine-grained PAT** | Granular permissions, scoped to specific repos. **Required** for org repos where classic PATs are restricted. |

Fine-grained PATs for org repos may require **org approval** (Settings → Personal access tokens → Pending requests).

---

## Owner Token (`GITHUB_OWNER_TOKEN`)

### Required Permissions (Fine-grained)

| Permission | Level | Used For |
|------------|-------|----------|
| Contents | **Read** | Fetch file contents at PR ref, repo tree |
| Pull requests | **Read and Write** | Read PR metadata, request reviewers |
| Issues | **Read** | Read existing PR comments |
| Issues | **Write** | Create tracker issues (optional) |
| Metadata | **Read** (auto-granted) | Discover repo structure |

### Required Permissions (Classic)

Select `repo` scope (full control). No separate issue permission needed — `repo` covers everything.

### Create (Fine-grained)

1. Go to https://github.com/settings/tokens?type=beta
2. **Generate new token** → **Fine-grained token**
3. **Resource owner**: the org (or your user) that owns the repo
4. **Repository access** → **Only select repositories** → pick the target repo
5. **Permissions** → **Repository permissions**:
   - **Contents**: **Read-only**
   - **Pull requests**: **Read and Write**
   - **Issues**: **Read and Write**
6. Generate, copy to `GITHUB_OWNER_TOKEN` in `.env`

### Create (Classic)

1. Go to https://github.com/settings/tokens
2. **Generate new token** → **Classic**
3. Select scopes: `repo` (full control)
4. Generate, copy to `GITHUB_OWNER_TOKEN` in `.env`
| `GET` | `/repos/{o}/{r}/pulls/{n}/reviews` | Owner | **Pull requests: Read** — reads latest review body |
| `POST` | `/repos/{o}/{r}/issues` | Owner | **Issues: Write** — creates a tracker issue |
| `GET` | `/user/repos` | Owner | **Metadata: Read** (auto-granted) — lists repositories to watch |


---

## Reviewer Token (`GITHUB_REVIEWER_TOKEN`)

### Required Permissions (Fine-grained)

| Permission | Level | Used For |
|------------|-------|----------|
| Pull requests | **Read and Write** | Submit reviews (approve/request changes/comment) |
| Issues | **Write** | Post fallback comments on the PR |
| Metadata | **Read** (auto-granted) | Look up PR info |

### Required Permissions (Classic)

Select `repo` scope.

### Create

Same steps as owner token. If the reviewer is a **separate bot account**, create the token under that account.

```
GITHUB_REVIEWER_TOKEN=github_pat_...
GITHUB_REVIEWER_USERNAME=my-bot-name
```



---

## Organization Repos

When the repo belongs to an org:

1. Set **Resource owner** to the **organization**, not your user
2. You need **org-level permissions** to authorize the token
3. Select **Only select repositories** and pick the target repo
4. If the org doesn't appear under "Resource owner", use a **classic PAT** instead

### Per-Org Token Overrides

When reviewing PRs across **multiple organizations**, a single fine-grained PAT
is scoped to one resource owner. Use per-org overrides to assign different
tokens per org:

```bash
# Default tokens (fallback)
GITHUB_OWNER_TOKEN=github_pat_default_...
GITHUB_REVIEWER_TOKEN=github_pat_default_...
GITHUB_REVIEWER_USERNAME=default-bot

# Overrides for org "my-company"
GITHUB_TOKEN_my-company_OWNER=github_pat_org_scoped_...
GITHUB_TOKEN_my-company_REVIEWER=github_pat_org_scoped_...
GITHUB_TOKEN_my-company_REVIEWER_USERNAME=org-bot
```

Resolution order per repo: `GITHUB_TOKEN_{org}_OWNER` → `GITHUB_OWNER_TOKEN` → `""`.

---

## Pre-Flight Verification

Before any review the app verifies both tokens independently:

1. `GET /user` with `Authorization: Bearer {t}` → **200** confirms the token exists and is not expired
2. `POST …/requested_reviewers` with `{"reviewers":[]}` → **201** confirms write access

Both checks are side-effect-free — the empty reviewers list triggers no notification. Verified `(org, role)` pairs are cached to `~/.config/pr-auto-reviewer/verified-tokens.json` so preflight runs only once per token per repo.

| HTTP status | Meaning |
|-------------|---------|
| **200** | Token is valid and has the required scope |
| **201** | Write access confirmed |
| **401** | Token does not exist — revoked, expired, or value is wrong |
| **403** | Token exists but lacks **Pull requests: Write** permission |
| **422** | Request body accepted but repo doesn't support the operation — treated as success |

Manual verification:

```bash
# Auth check (both tokens)
curl -s -w "HTTP %{http_code}\n" -o /dev/null \
  -H "Authorization: Bearer $GITHUB_OWNER_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  https://api.github.com/user

# Write access check — owner
curl -s -w "HTTP %{http_code}\n" -o /dev/null \
  -X POST \
  -H "Authorization: Bearer $GITHUB_OWNER_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/vnd.github.v3+json" \
  -d '{"reviewers":[]}' \
  https://api.github.com/repos/OWNER/REPO/pulls/PR/requested_reviewers

# Write access check — reviewer
curl -s -w "HTTP %{http_code}\n" -o /dev/null \
  -X POST \
  -H "Authorization: Bearer $GITHUB_REVIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -H "Accept: application/vnd.github.v3+json" \
  -d '{"reviewers":[]}' \
  https://api.github.com/repos/OWNER/REPO/pulls/PR/requested_reviewers
```
> The reviewer token can be the same as the owner token for a single-account setup.
| `GET` | `/repos/{o}/{r}/pulls` | Owner | **Pull requests: Read** — lists open PRs |