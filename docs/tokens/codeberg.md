# Codeberg / Forgejo Token Setup

Codeberg runs Forgejo — the API and token model are identical.

---

## Every HTTP Call This App Makes

| Method | Endpoint | Token | Required Scope |
|--------|----------|-------|----------------|
| `GET` | `/user` | Owner + Reviewer | `read:user` — validates token is not expired |
| `POST` | `/repos/{o}/{r}/pulls/{n}/requested_reviewers` | Owner + Reviewer | `write:repository` — empty reviewers list probes write access |
| `GET` | `/repos/{o}/{r}/pulls/{n}` | Owner | `read:repository` — fetches PR metadata |
| `GET` | `/repos/{o}/{r}/pulls/{n}.diff` | Owner | `read:repository` — fetches the unified diff |
| `GET` | `/repos/{o}/{r}/pulls/{n}/commits` | Owner | `read:repository` — fetches commit messages |
| `GET` | `/repos/{o}/{r}/raw/{sha}/{path}` | Owner | `read:repository` — fetches file contents at a commit |
| `GET` | `/repos/{o}/{r}/git/trees/{branch}?recursive=1` | Owner | `read:repository` — lists the repository file tree |
| `GET` | `/repos/{o}/{r}/raw/{branch}/{filename}` | Owner | `read:repository` — fetches conventions files |
| `POST` | `/repos/{o}/{r}/pulls/{n}/requested_reviewers` | Owner | `write:repository` — requests the bot as reviewer |
| `POST` | `/repos/{o}/{r}/pulls/{n}/reviews` | Reviewer | `write:repository` — submits the formal review |
| `POST` | `/repos/{o}/{r}/issues/{n}/comments` | Reviewer | `write:issue` — posts a comment on the PR |


---

## Scope System

Forgejo scopes are grouped by API route area:

| Scope | Level | Covers |
|-------|-------|--------|
| `repository` | `read` | `GET /repos/*`: list repos, get PRs, read files, read reviews |
| `repository` | `write` | `POST /repos/*`: submit reviews, request reviewers |
| `issue` | `read` | `GET /repos/*/issues/*/comments`: read PR comments |
| `issue` | `write` | `POST /repos/*/issues/*/comments`: post PR comments |
| `user` | `read` | `GET /user`: validate token during preflight |

A scope with `write` level **includes `read`** — no need to add both.

---

## Owner Token (`FORGEJO_OWNER_TOKEN`)

### Required Scopes

| Scope | Level | Used For |
|-------|-------|----------|
| `repository` | `read` | Fetch PR metadata, diff, files, repo tree, list PRs |
| `repository` | `write` | Request reviewers on the PR |
| `issue` | `read` | Read existing PR comments to compute item numbering |
| `issue` | `write` | Create tracker issues (optional — when issue tracking is enabled) |
| `user` | `read` | Preflight auth check |

### Create

1. Go to https://codeberg.org/settings/applications
2. **Generate New Token**
3. **Token name**: e.g. `pr-auto-reviewer-owner`
4. **Repository access**: choose depending on your needs:
   - **All (public, private, and limited)**: token works on all repos you can access
   - **Public only**: only public repos (read-only for private)
   - **Specific repositories**: only selected repos (only `read:repository`/`write:repository` and `read:issue`/`write:issue` scopes allowed)
5. **Permissions**: select `read:user`, `read:repository`, `write:repository`, `read:issue`, `write:issue`
6. Generate, copy to `FORGEJO_OWNER_TOKEN` in `.env`

---

## Reviewer Token (`FORGEJO_REVIEWER_TOKEN`)

### Required Scopes

| Scope | Level | Used For |
|-------|-------|----------|
| `repository` | `write` | Submit PR reviews |
| `issue` | `write` | Post fallback comments on the PR |
| `user` | `read` | Preflight auth check |

### Create

Same steps as owner token. If the reviewer is a **separate bot account**, generate the token under that account.

```
FORGEJO_REVIEWER_TOKEN=...
FORGEJO_REVIEWER_USERNAME=my-bot-name
```

| `GET` | `/repos/{o}/{r}/issues/{n}/comments` | Owner | `read:issue` — reads existing comments |
| `GET` | `/repos/{o}/{r}/pulls/{n}/reviews` | Owner | `read:repository` — reads latest review body |
| `POST` | `/repos/{o}/{r}/issues` | Owner | `write:issue` — creates a tracker issue |
| `GET` | `/user/repos` | Owner | `read:repository` — lists repositories to watch |
| `GET` | `/repos/{o}/{r}/pulls` | Owner | `read:repository` — lists open PRs |

> The reviewer token can be the same as the owner token for a single-account setup.

---

## Organization Repos

For org repos on Codeberg:

- The user generating the token must be a **member of the org**
- Under **Repository access**, choose **All** (the org's repos are included by membership)
- Or choose **Specific repositories** and pick the org repo explicitly
- No separate org approval workflow exists — membership is sufficient

---

## Pre-Flight Verification

Before any review the app verifies both tokens independently:

1. `GET /user` with `Authorization: token {t}` → **200** confirms the token exists and is not expired
2. `POST …/requested_reviewers` with `{"reviewers":[]}` → **201** or **422** confirms write access on the target repo

Both checks are side-effect-free — the empty reviewers list triggers no notification. Verified `(org, role)` pairs are cached to `~/.config/pr-auto-reviewer/verified-tokens.json` so preflight runs only once per token per repo.

| HTTP status | Meaning |
|-------------|---------|
| **200** | Token is valid and has the required scope |
| **201** | Write access confirmed (Codeberg returns 201 on success) |
| **401** | Token does not exist — revoked, expired, or value is wrong |
| **403** | Token exists but lacks `write:repository` scope |
| **422** | Request body accepted but repo doesn't support the operation — treated as success |

Manual verification:

```bash
# Auth check (both tokens)
curl -s -w "HTTP %{http_code}\n" -o /dev/null \
  -H "Authorization: token $FORGEJO_OWNER_TOKEN" \
  https://codeberg.org/api/v1/user

# Write access check — owner
curl -s -w "HTTP %{http_code}\n" -o /dev/null \
  -X POST \
  -H "Authorization: token $FORGEJO_OWNER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reviewers":[]}' \
  https://codeberg.org/api/v1/repos/OWNER/REPO/pulls/PR/requested_reviewers

# Write access check — reviewer
curl -s -w "HTTP %{http_code}\n" -o /dev/null \
  -X POST \
  -H "Authorization: token $FORGEJO_REVIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reviewers":[]}' \
  https://codeberg.org/api/v1/repos/OWNER/REPO/pulls/PR/requested_reviewers
```