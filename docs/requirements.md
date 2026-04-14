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

- **Codeberg**: https://codeberg.org/settings/applications
- **Forgejo**: `{forgejo_host}/user/settings/applications`

Required scopes:
- Owner: `repo`, `read:user`
- Reviewer: `repo`