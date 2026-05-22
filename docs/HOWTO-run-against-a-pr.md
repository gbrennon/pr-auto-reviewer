# How to Run a Review Against a Single PR

## Prerequisites

- `.env` configured with valid tokens (see [Configuration](configuration.md))
- Ollama running locally
- Python 3.14+

---

## Option 1: Python CLI (DDD Architecture)

Uses the new DDD-based review pipeline. Supports verbose mode for diagnostics.

```bash
python -m pr_auto_reviewer.cli review -r <owner/repo> -p <pr_number>
```

### Flags

| Flag | Description |
|------|-------------|
| `-r`, `--repo` | Repository in `owner/repo` format (required) |
| `-p`, `--pr` | PR number (required) |
| `--force` | Re-review even if already reviewed |
| `-v`, `--verbose` | Show detailed diagnostic output on errors |

### Examples

```bash
# Basic review
python -m pr_auto_reviewer.cli review -r gbrennon/BitPill -p 95

# Force re-review
python -m pr_auto_reviewer.cli review -r gbrennon/BitPill -p 95 --force

# With verbose diagnostics (shows open PR list on failure)
python -m pr_auto_reviewer.cli review -r gbrennon/BitPill -p 95 --force -v
```

### Verbose mode

Without `-v`, errors are a single shallow line:

```
Error: PR #12 not found or not open in gbrennon/dotfiles
```

With `-v`, you get diagnostic context:

```
[verbose] Fetching PR #12 from repository 'gbrennon/dotfiles'...
Error: PR #12 not found or not open in gbrennon/dotfiles
[verbose] 3 open PR(s) found: #1, #5, #8
```

---

## Option 2: Bash Script

Uses the shell-based pipeline. Works standalone without the Python bootstrap.

```bash
bash scripts/watch-prs.sh -r <owner/repo> -p <pr_number> --once
```

### Flags

| Flag | Description |
|------|-------------|
| `-r <repo>` | Repository in `owner/repo` format |
| `-p <pr>` | PR number |
| `--once` | Run a single cycle and exit |
| `-i <seconds>` | Poll interval (default: 60) |
| `--list-items` | Show review items without posting |

### Examples

```bash
# Review a single PR once
bash scripts/watch-prs.sh -r gbrennon/BitPill -p 95 --once

# Force re-review (uses -p without --once to skip duplicate check)
bash scripts/watch-prs.sh -r gbrennon/BitPill -p 95

# List extracted review items from the latest review
bash scripts/watch-prs.sh -r gbrennon/BitPill -p 95 --list-items
```

### Via Make

```bash
# Single PR review (wraps watch-prs.sh)
make review REPO=gbrennon/dotfiles PR=12
```

---

## Other Useful Commands

### Validate a PR locally

Generates the review and prints it to stdout without posting:

```bash
# Python
python -m pr_auto_reviewer.cli validate-pr -r owner/repo -p 12

# Bash
bash scripts/validate-pr.sh -r owner/repo -p 12
```

### Process issue commands for a PR

Checks comments for `/create-issue` commands and acts on them:

```bash
python -m pr_auto_reviewer.cli process-commands -r owner/repo -p 12

# With verbose
python -m pr_auto_reviewer.cli process-commands -r owner/repo -p 12 -v
```

### List review items

Extracts actionable items from a posted review:

```bash
python -m pr_auto_reviewer.cli list-items repo=owner/repo pr_number=12
```
