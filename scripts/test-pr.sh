#!/usr/bin/env bash
# test-pr.sh - Run test on a specific repo

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${1:-}"

if [[ -z "$REPO" ]]; then
    echo "Usage: $0 owner/repo"
    exit 1
fi

bash "${SCRIPT_DIR}/watch-prs.sh" -r "$REPO" --once