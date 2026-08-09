# Structure

This document explains the project structure and how the pieces fit together.

## Overview

The entry point is the Python CLI (`uv run python -m pr_auto_reviewer`).
All operations — bootstrap, PR watching, daemon management, command
processing — are handled by the Python application. Run `pr-auto-reviewer --help`
for available commands.


## Data Files

```
~/.config/pr-auto-reviewer/
├── state.json           # State file - tracks reviewed PRs by SHA
├── config               # Configuration file (env-file format)
└── verified-tokens.json # Token verification cache
```

The state file prevents duplicate reviews. A PR is only re-reviewed if the SHA changes.
