# Force Review

The force-review flag bypasses the idempotency guard and runs a full review even
when the PR was already reviewed at the same commit SHA.

## Why use it

Normally the daemon skips a PR when the head SHA hasn't changed since the last
review — the assumption is "nothing new, nothing to re-review". Force review
overrides that. Useful when:

- You tweaked the LLM prompt and want to see how the same diff fares.
- The model returned a malformed response and you want a retry.
- The prior review was published under the wrong token/username.

## How it works end-to-end

```
CLI (--pr N)
  → PollingDaemonConfig.force_pr = N
    → PollingDaemon._process_pr compares force_pr against each PR number
      → ReviewPullRequestCommand(force=True) … for the matching PR only
        → ReviewPullRequestService.execute skips the "already reviewed?" check
          → Full flow runs: diff → LLM → publish → save → dispatch
```

### Layer by layer

| Layer | What happens |
|---|---|
| `ReviewPullRequestCommand` | Carries `force: bool = False` (frozen dataclass). |
| `PollingDaemonConfig` | Stores `force_pr: Optional[int]` — the PR number to force. |
| `PollingDaemon._process_pr` | Compares `self._force_pr == pr.pr_id.number` and passes the result as `force` to the command. Logs `"Force-reviewing PR #…"` at INFO level when true. |
| `ReviewPullRequestService.execute` | Idempotency guard on line 62: `if not command.force and not pr.needs_review(...)` — a truthy `force` causes the whole condition be false, so the guard is skipped. |
| Log output | `"Force-reviewing PR #1 in owner/repo"` (daemon), then `"Starting review for PR … (SHA: …, force=True)"` (service). |

## Usage

### Via CLI

```bash
# Watch all repos, force re-review PR #42
pr-auto-reviewer watch-prs --once -p 42

# Single repo, force review, verbose logging
pr-auto-reviewer watch-prs -r owner/repo -p 42 -v
```

### Via environment variable

```bash
FORCE_PR=42 pr-auto-reviewer watch-prs --once
```

`FORCE_PR` is picked up in `bootstrap.py → run_daemon()` and fed into
`PollingDaemonConfig.force_pr`.

### Review command (single PR, new architecture)

```bash
pr-auto-reviewer review --repo owner/repo --pr 42
```

The `review` subcommand goes through `CliRunner._run_review` which currently
creates a `ReviewPullRequestCommand` with `force=False`. It can be extended to
accept a `--force` flag — see below.

## Extending the review subcommand with --force

The `review` subcommand currently does **not** pass the force flag. To add it:

1. `CliRunner._run_review` — add `add_argument("--force", action="store_true")`.
2. Pass `force=args.force` into `ReviewPullRequestCommand(...)`.

Patch sketch:

```python
# src/pr_auto_reviewer/presentation/cli/runner.py  (inside _run_review)
parser.add_argument("--force", action="store_true", help="Force review even if already reviewed")

command = ReviewPullRequestCommand(
    pr_id=pr.pr_id,
    head_sha=pr.head_sha,
    title=pr.title,
    force=args.force,       # ← added
)
```

And the CLI entry point:

```python
# src/pr_auto_reviewer/cli.py
review_parser.add_argument("--force", action="store_true", help="Force re-review")
```

## Tests that enforce this

| Test | What it proves |
|---|---|
| `test_force_bypasses_idempotency_guard` | `force=True` runs the full flow (diff, LLM, publish, save, dispatch) even when already reviewed at the same SHA. Verifies the "Starting review … force=True" log. |
| `test_force_pr_passes_force_flag` | When `force_pr=1` and PR #1 is processed, the dispatched command has `force=True` and the daemon logs `"Force-reviewing PR #1 …"`. |
| `test_force_pr_mismatched_does_not_set_force` | When `force_pr=2` but PR #1 is processed, the dispatched command has `force=False` and no "Force-reviewing" log is emitted. |
