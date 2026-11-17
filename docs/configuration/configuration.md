# Configuration

All configuration via environment variables, loaded from three sources
(lower number = higher priority):

1. **Shell environment** — direct exports
2. **Project `.env`** — repo root for dev/manual mode
3. **User config** — `~/.config/pr-auto-reviewer/config` for production/service mode

Application detects `ENV` to choose the load path.
Set `ENV=production` to use the user config file;
omit or set `ENV=development` to use the project `.env`.

## Contents

- [Required Variables](variables-and-output.md)
- [LLM Configuration](llm-daemon-and-prompts.md)
- [Per-Organisation Token Overrides](tokens-and-example.md)
