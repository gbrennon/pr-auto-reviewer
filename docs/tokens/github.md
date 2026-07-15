# GitHub Token Setup

## Token Types

| Type | When to use |
|------|-------------|
| **Classic PAT** | Simple setup, single user, no org approval needed. Works across all repos the user can access. |
| **Fine-grained PAT** | Granular permissions, scoped to specific repos. **Required** for org repos where classic PATs are restricted. |

Classic PATs with `repo` scope work everywhere but are broad. Fine-grained PATs are narrower but require org approval for org repos.

---

## Owner Token (`GITHUB_OWNER_TOKEN`)

### Permissions

| Permission | Required Level | Used For |
|------------|---------------|----------|
| Contents | **Read** | Fetch file contents at PR ref |
| Pull requests | **Read and Write** | Read PR metadata, request reviewers |
| Metadata | **Read** (auto-granted) | Discover repo structure |

### Create (Fine-grained)

1. Go to https://github.com/settings/tokens?type=beta
2. **Generate new token** → **Fine-grained token**
3. **Resource owner**: the org (or your user) that owns the repo
4. **Repository access** → **Only select repositories** → pick the target repo
5. **Permissions** → **Repository permissions**:
   - **Contents**: **Read-only**
   - **Pull requests**: **Read and Write**
6. Generate, copy to `GITHUB_OWNER_TOKEN` in `.env`

### Create (Classic)

1. Go to https://github.com/settings/tokens
2. **Generate new token** → **Classic**
3. Select scopes: `repo` (full control)
4. Generate, copy to `GITHUB_OWNER_TOKEN` in `.env`

---

## Reviewer Token (`GITHUB_REVIEWER_TOKEN`)

### Permissions

| Permission | Required Level | Used For |
|------------|---------------|----------|
| Pull requests | **Read and Write** | Submit reviews (approve/request changes/comment) |
| Metadata | **Read** (auto-granted) | Look up PR info |

Contents (Read) is only needed for inline comment positioning. Most setups include it.

### Create

Same steps as owner token. If the reviewer is a **separate bot account**, create the token under that account.

```
GITHUB_REVIEWER_TOKEN=github_pat_...
GITHUB_REVIEWER_USERNAME=my-bot-name
```

> The reviewer token can be the same as the owner token for a single-account setup.

---

## Organization Repos

When the repo belongs to an org:

1. Set **Resource owner** to the **organization**, not your user
2. You need **org-level permissions** to authorize the token
3. Select **Only select repositories** and pick the target repo
4. If the org doesn't appear under "Resource owner", use a **classic PAT** instead

Fine-grained PATs for org repos may require **org approval** (Settings → Personal access tokens → Pending requests) before they work.

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

# Overrides for org "another-org"
GITHUB_TOKEN_another-org_OWNER=github_pat_...
GITHUB_TOKEN_another-org_REVIEWER=github_pat_...
```

Resolution order per repo: `GITHUB_TOKEN_{org}_OWNER` → `GITHUB_OWNER_TOKEN` → `""`.

When no per-org override is set for an org, the default token is used (backwards
compatible). Classic PAT users see no behavior change.

---

## Pre-Flight Verification

```bash
# Read access
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -H "Authorization: Bearer $GITHUB_OWNER_TOKEN" \
  https://api.github.com/user
# Expect: 200

# Submit review (write test)
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST \
  -H "Authorization: Bearer $GITHUB_REVIEWER_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Content-Type: application/json" \
  -d '{"body":"preflight","event":"COMMENT"}' \
  https://api.github.com/repos/OWNER/REPO/pulls/PR/reviews
# Expect: 200 = write works, 403 = missing Pull requests: Write

# Request reviewer (owner write test)
curl -s -o /dev/null -w "HTTP %{http_code}\n" \
  -X POST \
  -H "Authorization: Bearer $GITHUB_OWNER_TOKEN" \
  -H "Accept: application/vnd.github.v3+json" \
  -H "Content-Type: application/json" \
  -d '{"reviewers":[]}' \
  https://api.github.com/repos/OWNER/REPO/pulls/PR/requested_reviewers
# 200/422 = write works, 403 = missing Pull requests: Write
```
