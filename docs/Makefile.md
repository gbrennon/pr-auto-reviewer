# Makefile Reference

This project includes a Makefile for convenient command-line operations.

## Quick Start

```bash
make help
```

## Available Targets

| Target | Description |
|--------|-------------|
| `make help` | Show this help message |
| `make install` | Run install script to configure the service |
| `make start` | Start the systemd service |
| `make stop` | Stop the systemd service |
| `make status` | Show service status |
| `make restart` | Restart the service |
| `make logs` | Follow service logs (Ctrl+C to exit) |
| `make watch` | Run watcher once in manual mode |
| `make test` | Run test review on a repo |
| `make issues` | Create issues from PR commands |
| `make list-items` | List items from review |
| `make clean` | Reset state file |

## Usage Examples

### Service Management

```bash
# Install and configure (first time only)
make install

# Start the watcher
make start

# Check if running
make status

# View logs in real-time
make logs

# Stop the service
make stop

# Restart after config changes
make restart
```

### Running Reviews

```bash
# Manual single run (watch all repos)
make watch

# Test review on specific repo
make test REPO=gbrennon/pr-auto-reviewer
```

### Issue Creation from Commands

```bash
# Create issues from PR #8
make issues REPO=gbrennon/pr-auto-reviewer PR=8

# List items in a PR review
make list-items REPO=gbrennon/pr-auto-reviewer PR=8
```

### Debugging

```bash
# View recent logs
journalctl --user -u pr-ai-auto-reviewer.service --no-pager -n 50

# Reset state (clears all reviewed PRs)
make clean

# Run with specific repo filter
bash scripts/watch-prs.sh -r owner/repo --once
```

## Environment Variables

Some targets accept environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `REPO` | Repository in owner/repo format | `gbrennon/pr-auto-reviewer` |
| `PR` | PR number | `8` |

## Common Workflows

### First Time Setup

```bash
# 1. Install the service
make install

# 2. Start it
make start

# 3. Check logs
make logs
```

### Manual Review Testing

```bash
# Run a single review cycle
make test REPO=your-username/test-repo
```

### Issue Creation Workflow

```bash
# 1. Post review (done automatically by watcher)
# 2. Add comment "create issue for 1, 2, 3" on PR
# 3. Run issue creation
make issues REPO=owner/repo PR=8

# Or list items first to see what's available
make list-items REPO=owner/repo PR=8
```

### Troubleshooting

```bash
# Service won't start
make status
journalctl --user -u pr-ai-auto-reviewer.service --no-pager -n 100

# API errors - check token
cat ~/.config/pr-auto-reviewer/config | grep TOKEN

# Ollama not running
curl http://localhost:11434/api/tags

# Force re-review a PR
bash scripts/watch-prs.sh -r owner/repo -p 8 --once

# Reset everything
make clean
make start
```