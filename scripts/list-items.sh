#!/usr/bin/env bash
# list-items.sh - List review items from a PR

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${1:-}"
PR="${2:-}"

if [[ -z "$REPO" ]] || [[ -z "$PR" ]]; then
    echo "Usage: $0 owner/repo pr-number"
    exit 1
fi

bash "${SCRIPT_DIR}/watch-prs.sh" -r "$REPO" -p "$PR" --list-items