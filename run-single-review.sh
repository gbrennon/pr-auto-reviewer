#!/usr/bin/env bash
# run-single-review.sh - Run a single review without formal installation

# Usage: ./run-single-review.sh <owner/repo> <pr_number> [terminal|platform]

set -e

REPO=$1
PR=$2
OUTPUT=${3:-terminal}

if [ -z "$REPO" ] || [ -z "$PR" ]; then
    echo "Usage: $0 <owner/repo> <pr_number> [terminal|platform]"
    echo "Example: $0 gbrennon/BitPill 95 terminal"
    exit 1
fi

# Ensure .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found. Please create one from .env.example"
    exit 1
fi

export REVIEW_OUTPUT="$OUTPUT"

# Try using 'uv run' for zero-install dependency management
if command -v uv >/dev/null 2>&1; then
    echo "[info] Using 'uv run' for zero-install execution..."
    uv run pr-auto-reviewer review --repo "$REPO" --pr "$PR" --force --verbose
else
    echo "[info] 'uv' not found, falling back to python -m..."
    export PYTHONPATH="src:."
    python -m pr_auto_reviewer.cli review --repo "$REPO" --pr "$PR" --force --verbose
fi
