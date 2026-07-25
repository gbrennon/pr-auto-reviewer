# Structure

This document explains the project structure and how the pieces fit together.

## Overview

The entry point is the Python CLI (`python -m pr_auto_reviewer`).
All operations — bootstrap, PR watching, daemon management, command
processing — are handled by the Python application. See `make help`
for available commands.


## Data Files

```
runner-data/
├── pr-reviews.json  # State file - tracks reviewed PRs by SHA
└── watch-prs.pid    # PID file for the watcher process
```

The state file prevents duplicate reviews. A PR is only re-reviewed if the SHA changes.
