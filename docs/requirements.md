# Requirements

## Software

- **Ollama** — Local AI inference server. Install from https://ollama.ai
- **systemd** — For service management on Linux
- **uv** — Python package manager. Install from https://docs.astral.sh/uv/
- **python3** — Python 3.10+
- **git** — For local repository cloning and diff computation

## Hardware

- **RAM**: 8GB+ recommended (depends on Ollama model)
- **Storage**: Minimal (state files only) + cache for git clones (~100MB per repo)
- **CPU**: Depends on Ollama model used

## Platform Support

| Platform | Status   |
|----------|----------|
| GitHub   | Tested   |
| Codeberg | Tested   |
| Forgejo  | Tested   |
| Gitea    | Should work |

## Accounts

Requires two accounts or one account with two tokens:

- **Owner** — reads PR data, requests reviewers
- **Reviewer** — submits the review (must differ from PR author)

## Tokens

See [docs/tokens/](tokens/README.md) for full instructions on token types, required permissions, and verification.

## Model

The default model is `code-review:latest`. Pull it with:

```bash
ollama pull code-review:latest
```

Or set `LLM_MODEL` to any model available in your Ollama instance.