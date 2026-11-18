# Configuration

Configuration is loaded from these sources, in precedence order (highest first):

1. **Shell environment** — direct exports
2. **Project `.env`** — repository root during development
3. **User config** — `~/.config/pr-auto-reviewer/config`
4. **TOML settings** — `~/.config/pr-auto-reviewer/settings.toml`

The settings CLI writes non-secret values to the TOML file:

```bash
uv run python -m pr_auto_reviewer config set POLL_INTERVAL 600
uv run python -m pr_auto_reviewer config get POLL_INTERVAL
```

Legacy `.env` and user-config values override TOML values when the same key exists.
Application detects `ENV` to choose the load path. Set `ENV=production` to use
user configuration; omit it or set `ENV=development` to use the project `.env`.

## Contents

- [Required Variables](variables-and-output.md)
- [LLM Configuration](llm-daemon-and-prompts.md)
- [Per-Organisation Token Overrides](tokens-and-example.md)
