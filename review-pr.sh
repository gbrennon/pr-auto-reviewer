#!/usr/bin/env bash
# Run fragment-based review for a PR
# Usage: ./review-pr.sh <PR_NUMBER> [terminal|platform]
set -e
cd "$(dirname "$0")"
PR="${1:?Usage: ./review-pr.sh <PR_NUMBER> [terminal|platform]}"
OUTPUT="${2:-terminal}"
export PYTHONPATH="src:."

if [ "$OUTPUT" = "platform" ]; then
    python scripts/review_with_fragments.py \
        --repo gbrennon/pr-auto-reviewer \
        --pr "$PR" \
        --language python \
        --model code-review \
        --output platform
else
    python scripts/review_with_fragments.py \
        --repo gbrennon/pr-auto-reviewer \
        --pr "$PR" \
        --language python \
        --model code-review \
        --output terminal
fi
