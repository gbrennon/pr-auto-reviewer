---
id: shell-shebang
language: shell
priority: 95
category: correctness
---

# Shell Shebang & Portability Review

Review the following shell script for proper shebang and portability:

```shell
{{ code }}
```

## Checks

- Missing shebang (`#!/bin/sh`, `#!/usr/bin/env bash`, etc.) on the first line
- Hardcoded `#!/bin/bash` when `#!/bin/sh` would suffice (POSIX portability)
- Using bash-specific features (`[[`, arrays, `source`) without `#!/usr/bin/env bash`
- Hardcoded interpreter paths that differ across systems (`#!/usr/local/bin/bash`)
- Missing executable permission flag indication
- Shebang with trailing options that may not be portable

## Good Example

```shell
#!/usr/bin/env bash
#
# deploy.sh — Deploy the application to the target environment.
#
# Requirements: bash 4+, rsync, ssh

set -euo pipefail

echo "Deploying to ${TARGET_HOST:?TARGET_HOST not set}..."
rsync -avz ./dist/ "${TARGET_HOST}:/var/www/app/"
echo "Deploy complete."
```

## Bad Example

```shell
# Missing shebang — script may run under wrong interpreter

echo "Deploying to $TARGET_HOST..."
rsync -avz ./dist/ $TARGET_HOST:/var/www/app/
```
