# LLM Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_HOST` | — | LLM API endpoint; must be explicitly configured |
| `LLM_MODEL` | — | Model name |
| `LLM_TIMEOUT` | `120` | Seconds before a generation request times out |
| `MAX_CONTEXT_TOKENS` | `24000` | Maximum chat history tokens sent to the LLM |
| `LLM_MAX_RETRIES` | `5` | Max retries on transient LLM errors |
| `REVIEW_MAX_RETRIES` | `1` | Max complete review attempts after a failed review |

`MAX_CONTEXT_TOKENS` limits the conversation history sent with each LLM request.
The default is `24000`, which is a conservative value for local model servers.
It is separate from the model server's advertised context window: a larger
server window does not guarantee that the host has enough memory to process a
large request safely.

Set the value in `~/.config/pr-auto-reviewer/config`, the project `.env`, or the
shell environment:

```bash
MAX_CONTEXT_TOKENS=131072
```

The shell environment has the highest precedence. Restart the daemon after
changing the setting so it reloads configuration:

```bash
pr-auto-reviewer restart
```

Use a lower value if the model server becomes slow or unavailable during long
reviews. Use a higher value only when the server has sufficient memory and the
review needs more conversation history.

## Daemon Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `POLL_INTERVAL` | `60` | Seconds between PR checks in watch mode |
| `RUN_ONCE` | `false` | Run one check cycle and exit |
| `REPOS_FILTER` | — | Single `owner/repo` to watch (empty = all repos, same as `-r` flag) |
| `REPOS_ALLOW_LIST` | — | Comma- or newline-separated exact repositories allowed in polling mode |
| `FORCE_PR` | — | PR number to re-review regardless of state |
| `DEBUG` | `false` | Enable debug logging (`1`, `true`, or `yes`) |
| `ENV` | `development` | Set to `production` to load from user config |

`REPOS_ALLOW_LIST` accepts comma- or newline-separated `owner/repo` entries.
Entries may include a platform prefix such as `github:owner/repo` or
`forgejo:owner/repo`; matching is case-insensitive and exact. The allow list
applies to polling mode and does not restrict the one-off `review` command.

## Prompt Tuning

| Variable | Default | Description |
|----------|---------|-------------|
| `MAX_PROMPT_TOKENS` | `9999` | Prompt token budget ceiling |
| `MAX_FILE_CHARS` | `3000` | Max characters per source file in prompt |
| `MAX_FILES` | `10` | Max files included in the review prompt |
| `MAX_STRUCTURE_LINES` | `100` | Max lines of repo structure in prompt |
| `USE_COMPACT_TEMPLATE` | `false` | Use the shorter prompt template |
| `USE_STRICT_FRAGMENT_SELECTION` | `false` | Only include fragments for changed files |
