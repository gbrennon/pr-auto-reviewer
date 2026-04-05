# Structure

This document explains the project structure and how the pieces fit together.

## Overview

The project has three main entry points:

```
scripts/
├── bootstrap.sh          # Primary entry point - use this to start
├── watch-prs.sh          # Main daemon - watches PRs and posts reviews
├── reload.sh             # Manual reload trigger
├── autostart/            # Service manager
│   ├── autostart.sh     # Main autostart controller
│   ├── 20-watch-prs.sh  # Service definition for PR watcher
│   └── lib.sh           # Autostart utilities
└── lib/                  # Shared libraries
    ├── env-loader.sh    # Environment loading
    ├── ollama-client.sh # Ollama API client
    ├── hot-reload.sh    # Config hot-reload
    ├── build-prompt.py  # Build Ollama prompt from diff
    ├── build-comment.py # Build review comment
    └── json-escape.py   # JSON escaping utility
```

## Entry Points

### bootstrap.sh

The recommended way to start the project. It:

1. Checks dependencies (curl, python3, flock, nohup)
2. Creates required directories (runner-data/)
3. Loads environment from `.env`
4. Checks if Ollama is running
5. Attempts to start Ollama if not running
6. Starts all autostart services

**Usage:**
```bash
bash scripts/bootstrap.sh
```

### watch-prs.sh

The main daemon that:

1. Polls Codeberg repos for open PRs
2. Skips draft PRs
3. Checks SHA against state file to avoid duplicate reviews
4. Fetches PR diff
5. Sends diff to Ollama
6. Posts review comment to Codeberg

**Usage:**
```bash
bash scripts/watch-prs.sh           # daemon mode, 60s interval
bash scripts/watch-prs.sh -i 30    # custom interval
bash scripts/watch-prs.sh -r owner/repo  # specific repo
bash scripts/watch-prs.sh --once    # single cycle
```

### autostart/

A simple service manager for running background processes. Similar to systemd but simpler.

**Usage:**
```bash
bash scripts/autostart/autostart.sh      # start all services
bash scripts/autostart/autostart.sh --stop   # stop all services
bash scripts/autostart/autostart.sh --status # show status
```

## Shared Libraries

### env-loader.sh

Loads environment variables from `.env` file. Used by bootstrap and autostart scripts to ensure consistent env across processes.

### ollama-client.sh

Provides utilities for talking to Ollama API:

- `ollama_available()` - Check if Ollama is running
- `resolve_ollama_host()` - Resolve the actual host URL (handles hot-reload)

### hot-reload.sh

Allows configuration changes without restarting:

- Monitors `.env` for changes
- Sends SIGHUP to watcher when config changes
- Watcher re-reads env on SIGHUP

### build-prompt.py

Takes a PR diff and builds a prompt for the Ollama model. The prompt instructs the AI to review code and provide structured feedback.

### build-comment.py

Takes the raw AI response and builds a formatted Markdown comment with:
- Verdict (Approved/Changes Requested)
- Issues found
- Suggestions
- Praise
- Summary

### json-escape.py

Utility to properly escape strings for JSON payloads.

## Data Files

```
runner-data/
├── pr-reviews.json  # State file - tracks reviewed PRs by SHA
└── watch-prs.pid    # PID file for the watcher process
```

The state file prevents duplicate reviews. A PR is only re-reviewed if the SHA changes.
