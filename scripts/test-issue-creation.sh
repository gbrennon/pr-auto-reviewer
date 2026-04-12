#!/usr/bin/env bash
# test-issue-creation.sh — Test issue creation from command
# Usage: bash scripts/test-issue-creation.sh owner/repo PR_NUMBER

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib/config-loader.sh"
load_config

API_BASE="${FORGEJO_HOST}/api/v1"
REPO="${1:-}"
PR_NUMBER="${2:-}"

if [[ -z "$REPO" ]] || [[ -z "$PR_NUMBER" ]]; then
  echo "Usage: $0 owner/repo pr-number"
  exit 1
fi

echo "Testing issue creation for PR #${PR_NUMBER} in ${REPO}"
echo

get_review_body() {
  curl -sf -H "Authorization: token ${FORGEJO_TOKEN}" \
    "${API_BASE}/repos/${REPO}/pulls/${PR_NUMBER}/reviews?limit=10" | python3 -c "
import sys, json
data = json.load(sys.stdin)
reviews = data if isinstance(data, list) else data.get('data', [])
if reviews:
    print(reviews[-1].get('body', ''))
" 2>/dev/null || true
}

get_comments() {
  curl -sf -H "Authorization: token ${FORGEJO_TOKEN}" \
    "${API_BASE}/repos/${REPO}/issues/${PR_NUMBER}/comments?limit=50" | python3 -c "
import sys, json
data = json.load(sys.stdin)
comments = data if isinstance(data, list) else data.get('data', [])
for c in comments:
    body = c.get('body', '')
    id = c.get('id', '')
    if body:
        print(f'{id}|{body}')
" 2>/dev/null || true
}

extract_items() {
  python3 -c "
import re, sys
body = sys.stdin.read()
items = []
for line in body.split('\n'):
    line = line.strip()
    if line.startswith('1. ') or line.startswith('2. ') or line.startswith('3. ') or \
       line.startswith('4. ') or line.startswith('5. ') or line.startswith('6. '):
        num = int(line[0])
        text = line[2:].strip()
        items.append(f'{num}|{text}')
for i in items:
    print(i)
" 2>/dev/null || true
}

parse_command() {
  python3 -c "
import re, sys
comment = sys.stdin.read().lower()
match = re.search(r'(?:create\s+issue\s+for\s+|issue\s+)([0-9,\s]+)', comment)
if match:
    nums = match.group(1)
    numbers = [n.strip() for n in re.split(r'[,\s]+', nums) if n.strip().isdigit()]
    print(','.join(numbers))
" 2>/dev/null || true
}

echo "=== Step 1: Get latest review body ==="
REVIEW_BODY=$(get_review_body)
if [[ -z "$REVIEW_BODY" ]]; then
  echo "ERROR: No review found"
  exit 1
fi
echo "Review found (${#REVIEW_BODY} chars)"
echo
echo "=== Step 2: Extract items ==="
ITEMS=$(echo "$REVIEW_BODY" | extract_items)
if [[ -z "$ITEMS" ]]; then
  echo "ERROR: No items extracted"
  echo "Sample of review:"
  echo "$REVIEW_BODY" | head -20
  exit 1
fi
echo "$ITEMS"
echo
echo "=== Step 3: Find command in comments ==="
COMMENTS=$(get_comments)
echo "$COMMENTS" | while IFS='|' read -r id body; do
  echo "Comment $id:"
  echo "  $body"
  CMD=$(echo "$body" | parse_command)
  if [[ -n "$CMD" ]]; then
    echo "  -> Command found: create issue for $CMD"
    echo "  -> Creating issues for: $CMD"
  fi
done