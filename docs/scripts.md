# Scripts Reference

## Make Commands

Run from project root:

| Command | Description |
|---------|-------------|
| `make test` | Run unit tests |
| `make install` | Install service and configure |
| `make start` | Start the watcher service |
| `make stop` | Stop the watcher service |
| `make status` | Show service status |
| `make restart` | Restart the service |
| `make logs` | Show service logs (follow mode) |
| `make watch` | Run watcher once manually |
| `make clean` | Reset state files |
| `make install-bashunit` | Install bashunit testing framework |

## Shell Scripts

### Installation

- `scripts/install-service.sh` - Install and configure systemd service

### Running

- `scripts/watch-prs.sh` - Main daemon, watches and reviews PRs
- `scripts/watch.sh` - Alias for watch-prs.sh --once

### Service Control

- `scripts/start.sh` - Start systemd service
- `scripts/stop.sh` - Stop systemd service
- `scripts/status.sh` - Check service status
- `scripts/restart.sh` - Restart service
- `scripts/logs.sh` - View logs

### Utilities

- `scripts/clean.sh` - Clear state files
- `scripts/test-unit.sh` - Run unit tests
- `scripts/install-bashunit.sh` - Install testing framework

### Issue Creation

- `scripts/create-issues-from-pr.sh` - Create issues from PR review comments

## Options

### watch-prs.sh Options

```bash
-r owner/repo  # Watch specific repo
-p PR_NUMBER   # Process specific PR
-i SECONDS    # Poll interval (default: 60)
--once        # Run single cycle
--list-items  # Show review items without posting
```