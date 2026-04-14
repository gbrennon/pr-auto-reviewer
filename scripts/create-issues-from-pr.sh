#!/usr/bin/env bash
# create-issues-from-pr.sh — Create issues from PR review comments
# Usage: bash scripts/create-issues-from-pr.sh owner/repo PR_NUMBER
#        bash scripts/create-issues-from-pr.sh owner/repo --all

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "${SCRIPT_DIR}/lib/config-loader.sh"
load_config

API_BASE="${FORGEJO_HOST}/api/v1"
REPO="${1:-}"
PR_NUMBER="${2:-}"

usage() {
  cat <<EOF
Usage: $(basename "$0") owner/repo [pr-number|--all]

Create issues from PR review commands.

Commands in comments:
  create issue for 1, 2, 3  - Create issues for items 1, 2, 3
  issue 1, 2               - Create issues for items 1, 2

The review must have been posted first with numbered items (1., 2., etc.)
EOF
  exit 0
}

get_pr_reviews() {
  local repo="$1"
  local pr_number="$2"
  
  curl -sf -H "Authorization: token ${FORGEJO_TOKEN}" \
    "${API_BASE}/repos/${repo}/pulls/${pr_number}/reviews?limit=10" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    reviews = data if isinstance(data, list) else data.get('data', [])
    for r in reviews:
        body = r.get('body', '')
        verdict = r.get('state', '')
        id = r.get('id', '')
        if body:
            print(f'{id}|{verdict}|{body}')
except Exception:
    pass
" 2>/dev/null || true
}

get_pr_comments() {
  local repo="$1"
  local pr_number="$2"
  
  curl -sf -H "Authorization: token ${FORGEJO_TOKEN}" \
    "${API_BASE}/repos/${repo}/issues/${pr_number}/comments?limit=50" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    comments = data if isinstance(data, list) else data.get('data', [])
    for c in comments:
        body = c.get('body', '')
        id = c.get('id', '')
        created = c.get('created_at', '')
        if body:
            print(f'{id}|{created}|{body}')
except Exception:
    pass
" 2>/dev/null || true
}

parse_command() {
  local comment="$1"
  
  echo "$comment" | python3 -c "
import re, sys
comment = sys.stdin.read().strip().lower()
match = re.search(r'(?:create\s+issue\s+for\s+|issue\s+)([0-9,\s]+)', comment)
if match:
    nums = match.group(1)
    numbers = [n.strip() for n in re.split(r'[,\s]+', nums) if n.strip() and n.strip().isdigit()]
    if numbers:
        print(','.join(numbers))
" 2>/dev/null || true
}

extract_review_items() {
  local review_body="$1"
  
  echo "$review_body" | python3 -c "
import re, sys
body = sys.stdin.read()
items = []
lines = body.split('\n')
in_issues = False
in_suggestions = False
next_num = 1

for line in lines:
    line = line.strip()
    if line.lower() == '### issues':
        in_issues = True
        in_suggestions = False
        continue
    elif line.lower() == '### suggestions':
        in_suggestions = True
        in_issues = False
        continue
    elif line.lower().startswith('### '):
        in_issues = False
        in_suggestions = False
        continue
    
    if in_issues or in_suggestions:
        # Match numbered: 1. text
        match = re.match(r'^(\d+)[\.\)]\s+(.*)', line)
        if match:
            num = int(match.group(1))
            text = match.group(2).strip()
            items.append(str(num) + '|' + text)
        # Match bullet: - text or * text
        elif line.startswith('- ') or line.startswith('* '):
            text = line.lstrip('-* ')
            if text:
                items.append(str(next_num) + '|' + text)
                next_num += 1

for i in items:
    print(i)
" 2>/dev/null || true
}

create_issue() {
  local repo="$1"
  local title="$2"
  local body="$3"
  
  local escaped_title
  local escaped_body
  escaped_title=$(echo "$title" | python3 "${SCRIPT_DIR}/lib/json_escape.py")
  escaped_body=$(echo "$body" | python3 "${SCRIPT_DIR}/lib/json_escape.py")
  
  local result
  result=$(curl -sf -X POST "${API_BASE}/repos/${repo}/issues" \
    -H "Authorization: token ${FORGEJO_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"title\":${escaped_title},\"body\":${escaped_body}}" 2>&1) || true
  
  local issue_number
  issue_number=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('number',''))" 2>/dev/null || true)
  
  echo "$issue_number"
}

post_comment() {
  local repo="$1"
  local pr_number="$2"
  local body="$3"
  
  local escaped_body
  escaped_body=$(echo "$body" | python3 "${SCRIPT_DIR}/lib/json_escape.py")
  
  curl -sf -X POST "${API_BASE}/repos/${repo}/issues/${pr_number}/comments" \
    -H "Authorization: token ${FORGEJO_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{\"body\":${escaped_body}}" 2>/dev/null || true
}

get_open_prs() {
  local repo="$1"
  
  curl -sf -H "Authorization: token ${FORGEJO_TOKEN}" \
    "${API_BASE}/repos/${repo}/pulls?state=open&limit=20" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    prs = data if isinstance(data, list) else data.get('data', [])
    for pr in prs:
        if pr.get('draft', False):
            continue
        num = pr.get('number', '')
        title = pr.get('title', '')
        sha = pr.get('head', {}).get('sha', '')
        if num and sha:
            print(f'{num}|{sha}|{title}')
except Exception:
    pass
" 2>/dev/null || true
}

process_pr() {
  local repo="$1"
  local pr_number="$2"
  
  echo "Processing PR #${pr_number}..."
  
  local reviews_json
  reviews_json=$(curl -sf -H "Authorization: token ${FORGEJO_TOKEN}" \
    "${API_BASE}/repos/${repo}/pulls/${pr_number}/reviews?limit=10" 2>/dev/null)
  
  if [[ -z "$reviews_json" ]]; then
    echo "  No reviews JSON"
    return
  fi
  
  local review_body
  review_body=$(python3 -c "
import sys, json
data = json.load(sys.stdin)
reviews = data if isinstance(data, list) else data.get('data', [])
print(reviews[0].get('body', ''), end='')
" <<< "$reviews_json")
  
  if [[ -z "$review_body" ]]; then
    echo "  No review body"
    return
  fi
  
  echo "  review body length: ${#review_body}"
  
  local review_items
  review_items=$(extract_review_items "$review_body")
  
  if [[ -z "$review_items" ]]; then
    echo "  No items found"
    return
  fi
  
  echo "  Found items: $review_items"
  
  local comments_json
  comments_json=$(curl -sf -H "Authorization: token ${FORGEJO_TOKEN}" \
    "${API_BASE}/repos/${repo}/issues/${pr_number}/comments?limit=50" 2>/dev/null)
  
  if [[ -z "$comments_json" ]]; then
    echo "  No comments"
    return
  fi
  
  echo "$comments_json" | python3 -c "
import sys, json
data = json.load(sys.stdin)
comments = data if isinstance(data, list) else data.get('data', [])
for c in comments:
    body = c.get('body', '')
    if body:
        print(f'{c.get(\"id\")}|{body[:50]}')
" 2>/dev/null | while IFS='|' read -r comment_id body; do
    [[ -z "$body" ]] && continue
    
    local cmd_numbers
    cmd_numbers=$(parse_command "$body")
    
    if [[ -z "$cmd_numbers" ]]; then
      continue
    fi
    
    echo "  Command in comment ${comment_id}: create issue for ${cmd_numbers}"
    
    local valid_items=()
    for num in $(echo "$cmd_numbers" | tr ',' '\n'); do
      if echo "$review_items" | grep -q "^${num}|"; then
        valid_items+=("$num")
      fi
    done
    
    for num in "${valid_items[@]}"; do
      local item_text
      item_text=$(echo "$review_items" | grep "^${num}|" | cut -d'|' -f2-)
      
      [[ -z "$item_text" ]] && continue
      
      local issue_title="[PR #${pr_number}] ${num}: ${item_text:0:200}"
      local issue_body="## Original Review (PR #${pr_number})
**Description:**
${item_text}
---
*Auto-created from PR #${pr_number} via PR AI Reviewer*"
      
      local issue_num
      issue_num=$(create_issue "$repo" "$issue_title" "$issue_body")
      
      if [[ -n "$issue_num" ]]; then
        echo "    Created issue #${issue_num}"
      fi
    done
  done
  
  echo "  Done"
}

if [[ -z "$REPO" ]]; then
  usage
fi

if [[ "$REPO" == "-h" ]] || [[ "$REPO" == "--help" ]]; then
  usage
fi

if [[ "$PR_NUMBER" == "--all" ]]; then
  echo "Processing all open PRs in ${REPO}..."
  for pr_line in $(get_open_prs "$REPO"); do
    pr_num=$(echo "$pr_line" | cut -d'|' -f1)
    process_pr "$REPO" "$pr_num"
  done
elif [[ -n "$PR_NUMBER" ]]; then
  process_pr "$REPO" "$PR_NUMBER"
else
  usage
fi