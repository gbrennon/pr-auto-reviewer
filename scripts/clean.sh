#!/usr/bin/env bash
# clean.sh - Clean state files

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Cleaning state files..."
rm -f "${PROJECT_DIR}/runner-data/pr-reviews.json"
echo '{"reviewed":{}}' > "${PROJECT_DIR}/runner-data/pr-reviews.json"
echo "Done. State reset."