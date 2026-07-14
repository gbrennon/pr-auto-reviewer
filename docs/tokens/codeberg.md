# Codeberg / Forgejo Token Setup

Codeberg runs Forgejo — the API and token model are identical.

---

## Scope System

Forgejo scopes are grouped by API route area. The relevant ones for this app:

| Scope | Level | Covers |
|-------|-------|--------|
| `repository` | `read` | `GET /repos/*`: list repos, get PRs, read files |
| `repository` | `write` | `POST/PUT/DELETE /repos/*`: submit reviews, request reviewers |
| `issue` | `write` | `POST /repos/issues/*/*/comments`: post issue comments on PRs |

A scope with `write` level **includes `read`** — no need to add both.

---

## Owner Token (`FORGEJO_OWNER_TOKEN`)

### Required Scopes

| Scope | Level | Used For |
|-------|-------|----------|
| `repository` | `read` | Fetch PR metadata, diff, files, repo tree |
| `repository` | `write` | Request reviewers on the PR |

Requesting a reviewer is a **notification step**, not a prerequisite for submitting a review. Anyone with `write:repository` can submit a review.

### Create

1. Go to https://codeberg.org/settings/applications
2. **Generate New Token**
3. **Token name**: e.g. `pr-auto-reviewer-owner`
4. **Repository access**: choose depending on your needs:
   - **All (public, private, and limited)**: token works on all repos you can access
   - **Public only**: only public repos (read-only for private)
   - **Specific repositories**: only selected repos (only `read:repository`/`write:repository` and `read:issue`/`write:issue` scopes allowed)
5. **Permissions**: select `read:repository` and `write:repository`
6. Generate, copy to `FORGEJO_OWNER_TOKEN` in `.env`

---

## Reviewer Token (`FORGEJO_REVIEWER_TOKEN`)

### Required Scopes

| Scope | Level | Used For |
|-------|-------|----------|
| `repository` | `write` | Submit PR reviews |
| `issue` | `write` | Post fallback comments on the PR |

### Create

Same steps as owner token. If the reviewer is a **separate bot account**, generate the token under that account.

```
FORGEJO_REVIEWER_TOKEN=...
FORGEJO_REVIEWER_USERNAME=my-bot-name
```

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

```bash
# Read access
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -H "Authorization: token $FORGEJO_OWNER_TOKEN" \
  https://codeberg.org/api/v1/user
# Expect: 200

# Request reviewer (owner write test)
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST \
  -H "Authorization: token $FORGEJO_OWNER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reviewers":[]}' \
  https://codeberg.org/api/v1/repos/OWNER/REPO/pulls/PR/requested_reviewers
# 201/422 = write works, 403 = missing write:repository

# Submit review (reviewer write test)
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST \
  -H "Authorization: token $FORGEJO_REVIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"body":"preflight","event":"COMMENT"}' \
  https://codeberg.org/api/v1/repos/OWNER/REPO/pulls/PR/reviews
# 201 = write works, 403 = missing write:repository

# Post comment (reviewer write test)
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST \
  -H "Authorization: token $FORGEJO_REVIEWER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"body":"preflight"}' \
  https://codeberg.org/api/v1/repos/OWNER/REPO/issues/PR/comments
# 201 = write works, 403 = missing issue:write
```
