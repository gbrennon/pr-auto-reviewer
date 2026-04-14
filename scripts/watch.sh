#!/usr/bin/env bash
# watch.sh - Run watcher once (manual mode)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "${SCRIPT_DIR}/watch-prs.sh" --once