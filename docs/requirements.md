# Requirements

## Software

- **Ollama** - Local AI inference server. Install from https://ollama.ai
- **systemd** - For service management on Linux
- **curl** - For API calls
- **python3** - For JSON processing
- **bash** - Shell scripts

## Hardware

- **RAM**: 8GB+ recommended (depends on Ollama model)
- **Storage**: Minimal (state files only)
- **CPU**: Depends on Ollama model used

## Platform Support

| Platform | Status |
|----------|--------|
| Codeberg | Tested |
| Forgejo | Tested |
| Gitea | Should work |

## Accounts

### Owner Account
- Generate token at platform settings
- Scopes: `repo`, `read:user`

### Reviewer Account
- Different account from owner
- Generate token at platform settings  
- Scopes: `repo`
- Username required for review attribution

## Tokens

Generate tokens from:

- **GitHub**: https://github.com/settings/tokens
- **Codeberg**: https://codeberg.org/settings/applications
- **Forgejo**: `{forgejo_host}/user/settings/applications`

Required scopes:
- Owner: `repo`, `read:user`
- Reviewer: `repo`

### GitHub token types

| Type | Instructions |
|------|-------------|
| **Classic PAT** | Create at https://github.com/settings/tokens with `repo` (all) and `read:user` scopes. Works for all orgs and repos the user has access to — no org-level configuration or approval needed. **Simpler; recommended for most users.** |
| **Fine-grained PAT** | Create at https://github.com/settings/tokens?type=beta. Requires explicit **Resource owner** (org) and **repository selection** — even for **public** repos. Must set `Read` access to `metadata` and `Administration`, `Write` access to `pull requests`, `contents`, and `issues`. |

⚠️ **Fine-grained PATs require org approval** (enabled by default since March 2025). Until an org owner approves the token at **Settings → Personal access tokens → Pending requests**, the token returns `401 Unauthorized` on non-public endpoints — including `/user`. If you see "Bad credentials" despite a freshly created token, the token is likely pending approval.

If the target org doesn't appear under "Resource owner", or you want to avoid the approval flow entirely, **use a classic PAT instead**.