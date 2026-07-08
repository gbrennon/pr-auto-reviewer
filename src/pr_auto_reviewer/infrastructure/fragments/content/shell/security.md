---
id: shell-security
language: shell
priority: 95
category: security
---

# Shell Security Review

Review the following shell script for security vulnerabilities:

```shell
{{ code }}
```

## Checks

- `eval` on user-supplied or unchecked input (arbitrary code execution)
- Command injection via unquoted variables in `ssh`, `find -exec`, `xargs`
- Piping `curl`/`wget` output directly into `sh`/`bash` without verification
- Insecure temporary files — predictable names in `/tmp` instead of `mktemp`
- Hardcoded secrets (passwords, API keys, tokens) in the script
- `sudo` inside scripts without restricting allowed commands
- `chmod 777` or overly permissive permissions
- Unsafe `export` of sensitive variables that may leak to child processes
- `read` from untrusted sources without input validation

## Good Example

```shell
#!/usr/bin/env bash
set -euo pipefail

readonly CONFIG_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/app.conf"

# Use mktemp for secure temp files
TEMP_FILE=$(mktemp) || exit 1
trap 'rm -f "$TEMP_FILE"' EXIT

# Validate input before use
if [[ ! "$1" =~ ^[a-zA-Z0-9_-]+$ ]]; then
    echo "ERROR: Invalid project name" >&2
    exit 1
fi
project_name="$1"

# Never pipe curl into shell
# BAD:  curl -s https://example.com/install.sh | bash
# GOOD: download, inspect, then run
curl -fsSLo "${TEMP_FILE}" "https://example.com/${project_name}/release.tar.gz"
sha256sum -c "${TEMP_FILE}.sha256" || exit 1
tar xzf "$TEMP_FILE"
```

## Bad Example

```shell
#!/bin/bash

# Hardcoded secret
API_KEY="sk-abc123xyz"

# eval with user input
eval "echo User input: $1"

# Pipe untrusted URL into shell
curl -s "https://$1.example.com/install.sh" | bash

# Predictable temp file
echo "processing" > /tmp/result.txt
```
