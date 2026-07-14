# Requirements

## Software

- **Ollama** — Local AI inference server. Install from https://ollama.ai
- **systemd** — For service management on Linux
- **curl** — For API calls
- **python3** — For JSON processing
- **bash** — Shell scripts

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

Requires two accounts or one account with two tokens:

- **Owner** — reads PR data, requests reviewers
- **Reviewer** — submits the review (must differ from PR author)

## Tokens

See [docs/tokens/](tokens/README.md) for full instructions on token types, required permissions, and verification.
