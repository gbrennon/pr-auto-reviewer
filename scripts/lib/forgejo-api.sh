#!/usr/bin/env bash
# forgejo-api.sh — Single Responsibility: Forgejo/Codeberg API integration

FORGEJO_API_HOST="${FORGEJO_HOST:-https://codeberg.org}"
FORGEJO_API_BASE="${FORGEJO_API_HOST}/api/v1"
FORGEJO_TOKEN="${FORGEJO_TOKEN:-}"

forgejo_api_get() {
  local endpoint="$1"
  curl -sf -H "Authorization: token ${FORGEJO_TOKEN}" "${FORGEJO_API_BASE}${endpoint}" 2>/dev/null || true
}

forgejo_api_post() {
  local endpoint="$1"
  local data="$2"
  curl -sf -X POST -H "Authorization: token ${FORGEJO_TOKEN}" \
    -H "Content-Type: application/json" \
    -d "$data" "${FORGEJO_API_BASE}${endpoint}" 2>/dev/null || true
}

forgejo_get_user_repos() {
  local username
  username=$(forgejo_api_get "/user" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('login') or data.get('username') or '')
except Exception:
    pass
" 2>/dev/null || true)

  if [[ -z "$username" ]]; then
    return 0
  fi

  forgejo_api_get "/user/repos?limit=50" | python3 -c "
import sys, json
owner = '${username}'
try:
    data = json.load(sys.stdin)
    if isinstance(data, list):
        for r in data:
            full_name = r.get('full_name', '')
            repo_owner = r.get('owner', {}).get('login') or r.get('owner', {}).get('username') or ''
            if full_name.startswith(owner + '/') or repo_owner == owner:
                print(full_name)
    elif isinstance(data, dict):
        for r in data.get('data', []):
            full_name = r.get('full_name', '')
            repo_owner = r.get('owner', {}).get('login') or r.get('owner', {}).get('username') or ''
            if full_name.startswith(owner + '/') or repo_owner == owner:
                print(full_name)
except Exception:
    pass
" 2>/dev/null || true
}

forgejo_get_open_prs() {
  local repo="$1"
  forgejo_api_get "/repos/${repo}/pulls?state=open&limit=20" | python3 -c "
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

forgejo_get_pr_diff() {
  local repo="$1"
  local pr_number="$2"
  forgejo_api_get "/repos/${repo}/pulls/${pr_number}.diff" 2>/dev/null || true
}

forgejo_get_pr_comments() {
  local repo="$1"
  local pr_number="$2"
  forgejo_api_get "/repos/${repo}/pulls/${pr_number}/comments?limit=50" | python3 -c "
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

forgejo_get_pr_reviews() {
  local repo="$1"
  local pr_number="$2"
  forgejo_api_get "/repos/${repo}/pulls/${pr_number}/reviews?limit=10" | python3 -c "
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

forgejo_post_pr_review() {
  local repo="$1"
  local pr_number="$2"
  local event="$3"
  local body="$4"
  local reviewer_token="$5"
  
  local escaped_body
  escaped_body=$(echo "$body" | python3 "${SCRIPT_DIR}/lib/json_escape.py")
  
  forgejo_api_post "/repos/${repo}/pulls/${pr_number}/reviews" \
    "{\"event\":\"${event}\",\"body\":${escaped_body}}" \
    -H "Authorization: token $reviewer_token" \
    -H "accept: application/json" 2>/dev/null || true
}

forgejo_request_reviewer() {
  local repo="$1"
  local pr_number="$2"
  local reviewer_username="$3"
  
  forgejo_api_post "/repos/${repo}/pulls/${pr_number}/requested_reviewers" \
    "{\"reviewers\":[\"$reviewer_username\"]}" 2>/dev/null || true
}

forgejo_create_issue() {
  local repo="$1"
  local title="$2"
  local body="$3"
  
  local escaped_title
  local escaped_body
  escaped_title=$(echo "$title" | python3 "${SCRIPT_DIR}/lib/json_escape.py")
  escaped_body=$(echo "$body" | python3 "${SCRIPT_DIR}/lib/json_escape.py")
  
  local result
  result=$(forgejo_api_post "/repos/${repo}/issues" \
    "{\"title\":${escaped_title},\"body\":${escaped_body}}")
  
  echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('number',''))" 2>/dev/null || true
}

forgejo_post_comment() {
  local repo="$1"
  local pr_number="$2"
  local body="$3"
  
  local escaped_body
  escaped_body=$(echo "$body" | python3 "${SCRIPT_DIR}/lib/json_escape.py")
  
  forgejo_api_post "/repos/${repo}/pulls/${pr_number}/comments" \
    "{\"body\":${escaped_body}}" 2>/dev/null || true
}

forgejo_get_repo_tree() {
  local repo="$1"
  local ref="${2:-main}"
  
  forgejo_api_get "/repos/${repo}/git/trees/${ref}?recursive=true" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tree = data.get('tree', [])
    for entry in tree:
        path = entry.get('path', '')
        entry_type = 'dir' if entry.get('type') == 'tree' else 'file'
        suffix = '/' if entry_type == 'dir' else ''
        print(f'{path}{suffix}')
except Exception:
    pass
" 2>/dev/null || true
}

forgejo_get_file_content() {
  local repo="$1"
  local ref="${2:-main}"
  local path="$3"
  
  forgejo_api_get "/repos/${repo}/raw/${ref}/${path}" 2>/dev/null || true
}
