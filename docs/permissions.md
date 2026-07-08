# Permissions

This document describes the tokens, scopes, and verification steps
required for the PR AI Auto-Reviewer on Forgejo/Codeberg and GitHub.

---

## Forgejo / Codeberg

Codeberg runs Forgejo — the API and token model are the same.

**Generate tokens at:** https://codeberg.org/settings/applications

### Available Scopes

| Field | Permission | Description |
|---|---|---|
| `user` | read | Get user profile, subscriptions, settings |
| `user` | write | Update user subscriptions, settings |
| `repository` | read | Get repository files, releases, collaborators |
| `repository` | write | Push/pull files, manage PRs, post reviews, request reviewers |
| `issue` | read | Get issue comments, attachments, milestones |
| `issue` | write | Post/edit issue comments, update milestones |
| `activitypub` | read | ActivityPub read operations |
| `activitypub` | write | ActivityPub write/delete operations |
| `misc` | read | Get label and gitignore templates |
| `misc` | write | Markup utility operations |
| `notification` | read | Read user notifications |
| `notification` | write | Mark notifications as read |
| `organization` | read | List organizations and teams |
| `organization` | write | Create/update teams and org settings |
| `package` | read | Read and download packages |
| `package` | write | Same as read currently |

### FORGEJO_OWNER_TOKEN

This token performs read-heavy operations:

| Action | Endpoint | Method | Required Scope |
|---|---|---|---|
| List repos | `/repos/search` | GET | `repository` (read) |
| List open PRs | `/repos/{o}/{r}/pulls` | GET | `repository` (read) |
| Get PR details | `/repos/{o}/{r}/pulls/{n}` | GET | `repository` (read) |
| Get PR diff | `/repos/{o}/{r}/pulls/{n}.diff` | GET | `repository` (read) |
| Get raw file | `/repos/{o}/{r}/raw/{ref}/{path}` | GET | `repository` (read) |
| Get tree | `/repos/{o}/{r}/git/trees/{ref}` | GET | `repository` (read) |
| Request reviewer | `/repos/{o}/{r}/pulls/{n}/requested_reviewers` | POST | `repository` (write) |

**Minimum scopes:**

| Scope | Permission |
|---|---|
| `repository` | read |
| `repository` | write |

> `write` is needed because the owner token requests the reviewer on the PR
> (and the reviewer cannot be the PR author — Codeberg returns 422: `"poster of pr can't be reviewer"`).
> Requesting a reviewer is a **notification/UX step**, not a prerequisite for submitting a review.
> Anyone with write access (and a token with `repository` write scope) can submit a review.
> **Exception:** You cannot review your own PR — self-review is blocked.

### FORGEJO_REVIEWER_TOKEN

This token posts the actual review:

| Action | Endpoint | Method | Required Scope |
|---|---|---|---|
| Submit review | `/repos/{o}/{r}/pulls/{n}/reviews` | POST | `repository` (write) |

**Minimum scopes:**

| Scope | Permission |
|---|---|
| `repository` | write |

### Verify Forgejo Tokens

```bash
# Verify OWNER token exists and has read access
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -H "Authorization: token $FORGEJO_OWNER_TOKEN" \
  https://codeberg.org/api/v1/user
# Must return 200. If 401, the token is invalid or expired.

# Verify REVIEWER token exists
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -H "Authorization: token $FORGEJO_REVIEWER_TOKEN" \
  https://codeberg.org/api/v1/user
# Must return 200.

# Verify owner can request a reviewer
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST \
  -H "Authorization: token $FORGEJO_OWNER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reviewers":["USERNAME"]}' \
  https://codeberg.org/api/v1/repos/OWNER/REPO/pulls/PR/requested_reviewers
# 201 = requested, 422 = already requested (both OK), 403 = insufficient scope

# Verify reviewer can submit a review
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST \
  -H "Authorization: token $FORGEJO_REVIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"body":"test","event":"COMMENT"}' \
  https://codeberg.org/api/v1/repos/OWNER/REPO/pulls/PR/reviews
# 201 = review posted, 401 = invalid token, 403 = insufficient scope
```

---

## GitHub

**Generate tokens at:** https://github.com/settings/tokens

### GITHUB_OWNER_TOKEN

| Action | Endpoint | Method | Required Scope |
|---|---|---|---|
| List repos | `/user/repos` | GET | `repo` |
| List PRs | `/repos/{o}/{r}/pulls` | GET | `repo` |
| Get PR | `/repos/{o}/{r}/pulls/{n}` | GET | `repo` |
| Get diff | `/repos/{o}/{r}/pulls/{n}` | GET | `repo` |
| Request reviewer | `/repos/{o}/{r}/pulls/{n}/requested_reviewers` | POST | `repo` |

**Minimum:** Classic token with `repo` scope, **or** fine-grained PAT with:

| Permission | Level |
|---|---|
| Pull requests | Read and write |
| Metadata | Read |
| Contents | Read |

### GITHUB_REVIEWER_TOKEN

| Action | Endpoint | Method | Required Scope |
|---|---|---|---|
| Submit review | `/repos/{o}/{r}/pulls/{n}/reviews` | POST | `repo` |

**Minimum:** Classic token with `repo` scope, **or** fine-grained PAT with:

| Permission | Level |
|---|---|
| Pull requests | Read and write |
| Metadata | Read |

> The reviewer must also have **write/push access** to the repository.
> If the reviewer is the PR author, self-review is blocked.

### Verify GitHub Tokens

```bash
# Verify OWNER token
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -H "Authorization: Bearer $GITHUB_OWNER_TOKEN" \
  https://api.github.com/user
# Must return 200.

# Verify REVIEWER token
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -H "Authorization: Bearer $GITHUB_REVIEWER_TOKEN" \
  https://api.github.com/user
# Must return 200.

# Verify reviewer can submit a review
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST \
  -H "Authorization: Bearer $GITHUB_REVIEWER_TOKEN" \
  -H "Accept: application/vnd.github+json" \
  -H "Content-Type: application/json" \
  -d '{"body":"test","event":"COMMENT"}' \
  https://api.github.com/repos/OWNER/REPO/pulls/PR/reviews
# 200 = review posted, 401 = invalid token, 403 = insufficient scope
```

---

## Header Format (critical)

```
Forgejo / Codeberg:  Authorization: token {token}
GitHub:              Authorization: Bearer {token}
```

Using the wrong prefix causes 401 even with a valid token.

---

## Ollama

No authentication required. Ensure Ollama is running at the configured host.
