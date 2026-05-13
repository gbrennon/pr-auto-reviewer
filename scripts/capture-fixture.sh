#!/usr/bin/env bash
# Capture a PR's diff AND its LLM review as test fixtures.
# Review is ALWAYS generated. Works with open, closed, or merged PRs.
# Fixture name is auto-generated: {owner}-{repo}-pr{number}
#
# Usage:
#   make capture-fixture REPO=gbrennon/pr-auto-reviewer PR=53
#   bash scripts/capture-fixture.sh -r gbrennon/pr-auto-reviewer -p 53

set -euo pipefail

REPO=""
PR=""
NAME=""

while [[ $# -gt 0 ]]; do
  case $1 in
    -r) REPO="$2"; shift 2 ;;
    -p) PR="$2"; shift 2 ;;
    -n) NAME="$2"; shift 2 ;;   # optional: override auto-generated name
    -*) echo "Unknown option: $1" >&2; exit 1 ;;
    *) shift ;;
  esac
done

if [ -z "$REPO" ] || [ -z "$PR" ]; then
  echo "Error: -r <repo> and -p <pr_number> are required" >&2
  exit 1
fi

# Load token from .env if not already set
if [ -z "${FORGEJO_TOKEN:-}" ]; then
  if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
  fi
fi

if [ -z "${FORGEJO_TOKEN:-}" ]; then
  echo "Error: FORGEJO_TOKEN not set" >&2
  exit 1
fi

API_BASE="https://codeberg.org/api/v1"
OUT_DIR="tests/fixtures"
DIFF_DIR="$OUT_DIR/diffs"
REVIEW_DIR="$OUT_DIR/reviews"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

mkdir -p "$DIFF_DIR" "$REVIEW_DIR"

# --- Fetch PR metadata ---
PR_DATA=$(curl -sf -H "Authorization: token ${FORGEJO_TOKEN}" \
  "${API_BASE}/repos/${REPO}/pulls/${PR}" 2>/dev/null || true)

HEAD_SHA=$(echo "$PR_DATA" | python3 -c "import sys,json; print(json.load(sys.stdin).get('head',{}).get('sha',''))" 2>/dev/null || echo "")
TITLE=$(echo "$PR_DATA" | python3 -c "import sys,json; print(json.load(sys.stdin).get('title',''))" 2>/dev/null || echo "")
OWNER=$(echo "$REPO" | cut -d'/' -f1)
REPO_NAME=$(echo "$REPO" | cut -d'/' -f2)

# Auto-generate fixture name from repo + PR if not explicitly provided
FIXTURE_NAME="${NAME:-${OWNER}-${REPO_NAME}-pr${PR}}"


# --- Remove any existing fixture with the same repo+PR (different name) ---
for existing_meta in "$DIFF_DIR"/*.json; do
  [ -f "$existing_meta" ] || continue
  existing_repo=$(python3 -c "import json; print(json.load(open('$existing_meta')).get('full_repo',''))" 2>/dev/null || echo "")
  existing_pr=$(python3 -c "import json; print(json.load(open('$existing_meta')).get('pr_number',''))" 2>/dev/null || echo "")
  if [ "$existing_repo" = "$REPO" ] && [ "$existing_pr" = "$PR" ]; then
    existing_name=$(basename "$existing_meta" .json)
    if [ "$existing_name" != "$FIXTURE_NAME" ]; then
      rm -f "$DIFF_DIR/${existing_name}.diff" "$DIFF_DIR/${existing_name}.json" "$REVIEW_DIR/${existing_name}.json"
      echo "  [cleanup] Removed stale fixture '${existing_name}' (replaced by '${FIXTURE_NAME}')"
    fi
  fi
done

echo "Capturing fixture '${FIXTURE_NAME}' from ${REPO}#${PR} ..."
echo "  Head SHA: ${HEAD_SHA:0:10}..."
echo "  Title: $TITLE"

# --- 1. Capture diff ---
DIFF=$(curl -sf -H "Authorization: token ${FORGEJO_TOKEN}" \
  "${API_BASE}/repos/${REPO}/pulls/${PR}.diff" 2>/dev/null || true)

if [ -z "$DIFF" ]; then
  echo "Error: Failed to fetch diff" >&2
  exit 1
fi

DIFF_FILE="$DIFF_DIR/${FIXTURE_NAME}.diff"
META_FILE="$DIFF_DIR/${FIXTURE_NAME}.json"

echo "$DIFF" > "$DIFF_FILE"
echo "  [diff]  $DIFF_FILE ($(wc -c < "$DIFF_FILE") bytes)"

# --- Save metadata alongside diff ---
python3 "$SCRIPT_DIR/_save_meta.py" "$OWNER" "$REPO_NAME" "$REPO" "$PR" "$HEAD_SHA" "$TITLE" "$META_FILE"
echo "  [meta]  ${META_FILE}"


# --- 2. Generate LLM review ---
REVIEW_FILE="$REVIEW_DIR/${FIXTURE_NAME}.json"
echo ""
echo "  Generating LLM review (this may take a minute)..."
python3 "$SCRIPT_DIR/_generate_review.py" \
  "$DIFF_FILE" "$REVIEW_FILE" \
  --repo "$REPO" \
  --owner "$OWNER" \
  --repo-name "$REPO_NAME" \
  --pr "$PR" \
  --sha "$HEAD_SHA"
echo "  [review] ${REVIEW_FILE}"

echo ""
echo "Done! Fixture '${FIXTURE_NAME}' captured."
