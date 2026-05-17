# New Fragment-Based Review Commands

These commands use the Python `CompositionRoot` pipeline with fragment-based
prompt composition (`ReviewContextFactory` → `ComposeReviewPromptService`).

## Quick reference

```bash
# All repos, continuous loop (Ctrl+C to stop):
make review-new-all

# Single repo, all open PRs, single cycle:
make review-new REPO=gbrennon/ModDar

# Single repo, single cycle, force specific PR (even if already reviewed):
FORCE_PR=2 make review-new REPO=gbrennon/ModDar

# Single PR, always force-reviewed:
make review-new-pr REPO=gbrennon/ModDar PR=2
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `POLL_INTERVAL` | `60` | Seconds between cycles (`review-new-all` only) |
| `REVIEW_OUTPUT` | `codeberg` | `terminal` prints locally, `codeberg` posts to platform |
| `DEBUG` | `0` | Set to `1` for verbose output (full prompt, full response, per-item breakdown) |
| `REPOS_FILTER` | (all) | Limit to specific repos, e.g. `gbrennon/ModDar` |

## Examples

```bash
# Terminal mode, verbose, 30s interval:
DEBUG=1 REVIEW_OUTPUT=terminal POLL_INTERVAL=30 make review-new-all

# Force re-review PR #2 on ModDar, terminal only:
REVIEW_OUTPUT=terminal make review-new-pr REPO=gbrennon/ModDar PR=2

# Post real reviews to codeberg, all repos:
make review-new-all
```

## Legacy (bash) commands for comparison

```bash
make review REPO=gbrennon/ModDar PR=2        # old bash path
```
