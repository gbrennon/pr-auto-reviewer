---
id: shell-error-handling
language: shell
priority: 90
category: error-handling
---

# Shell Error Handling Review

Review the following shell script for proper error handling:

```shell
{{ code }}
```

## Checks

- Missing `set -e` (exit on error) — commands can fail silently
- Missing `set -u` (error on unset variable) — typos silently expand to empty
- Missing `set -o pipefail` — pipeline exit status is only the last command
- Unchecked exit codes from critical commands (`rm`, `mv`, `curl`, `ssh`)
- Missing `trap` for cleanup on exit or interrupt (`EXIT`, `INT`, `TERM`)
- `cd` without checking success (subsequent commands run in wrong directory)
- Background processes without `wait` to check their exit status
- `rm -rf` with unvalidated variables that could expand dangerously

## Good Example

```shell
#!/usr/bin/env bash
set -euo pipefail

cleanup() {
    local exit_code=$?
    rm -rf "${TEMP_DIR:-}"
    echo "Cleanup complete (exit $exit_code)"
    exit "$exit_code"
}
trap cleanup EXIT INT TERM

TEMP_DIR=$(mktemp -d)

cd "${PROJECT_DIR:?PROJECT_DIR not set}" || {
    echo "ERROR: Cannot cd to $PROJECT_DIR" >&2
    exit 1
}

if ! curl -fsSL "$DOWNLOAD_URL" -o "$TEMP_DIR/archive.tar.gz"; then
    echo "ERROR: Download failed" >&2
    exit 1
fi
```

## Bad Example

```shell
#!/bin/bash

cd $PROJECT_DIR
# No error check — if cd fails, subsequent commands run in wrong directory

curl "$URL" -o output.tar.gz
# No -f flag — curl exits 0 even on HTTP 404

tar xzf output.tar.gz
rm output.tar.gz
# No cleanup on interrupt — temp files may be left behind
```
