#!/usr/bin/env bash
# watch-prs.sh — Daemon that watches Codeberg repos for open PRs and posts AI reviews.
#
# Flow:
#   1. Poll configured Codeberg repos for open PRs
#   2. Check SHA against state file
#   3. If new/updated: fetch diff, send to Ollama, post review
#
# Usage:
#   ./watch-prs.sh                    # daemon mode, 60s interval
#   ./watch-prs.sh -i 30             # custom interval
#   ./watch-prs.sh -r owner/repo     # watch specific repo
#   ./watch-prs.sh --once            # single cycle

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Lock
WATCHER_LOCK_FILE="${REPO_ROOT}/watcher-prs.lock"
WATCHER_PID_FILE="${REPO_ROOT}/watcher-prs.pid"
exec 9>"$WATCHER_LOCK_FILE"
if ! flock -n 9; then
  echo "watch-prs.sh is already running. Exiting." >&2
  exit 1
fi
echo $$ > "$WATCHER_PID_FILE"

trap 'rm -f "$WATCHER_PID_FILE"' EXIT INT TERM

# Hot-reload support
source "${SCRIPT_DIR}/lib/hot-reload.sh"
init_hot_reload "$REPO_ROOT"

# Load config from ~/.config/pr-auto-reviewer/config or repo .env
source "${SCRIPT_DIR}/lib/config-loader.sh"
load_config

# Config
FORGEJO_HOST="${FORGEJO_HOST:-https://codeberg.org}"
FORGEJO_TOKEN="${FORGEJO_TOKEN:-}"
API_BASE="${FORGEJO_HOST}/api/v1"
INTERVAL="${POLL_INTERVAL:-60}"
REPOS_FILTER=""
RUN_ONCE=false
STATE_FILE="${REPO_ROOT}/runner-data/pr-reviews.json"

# Ollama settings
source "${SCRIPT_DIR}/lib/ollama-client.sh"
OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-code-review}"

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Watch Codeberg repos for open PRs and post AI reviews.

Options:
  -i <seconds>      Poll interval (default: ${INTERVAL})
  -r <repo>         Watch specific repo (e.g., gbrennon/BitPill)
  --once            Single cycle
  -h, --help        This help

Environment:
  POLL_INTERVAL     Interval in seconds (default: 60)
  FORGEJO_TOKEN   API token for Codeberg (required for private repos)
  OLLAMA_HOST       Ollama endpoint (default: http://localhost:11434)
  OLLAMA_MODEL      Model to use (default: code-review)

State:
  ${STATE_FILE}
EOF
  exit 0
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -i) INTERVAL="$2"; shift 2 ;;
    -r) REPOS_FILTER="$2"; shift 2 ;;
    --once) RUN_ONCE=true; shift ;;
    -h|--help) usage ;;
    *) echo "Unknown: $1" >&2; usage ;;
  esac
done

init_state() {
  mkdir -p "$(dirname "$STATE_FILE")"
  if [[ ! -f "$STATE_FILE" ]]; then
    echo '{"reviewed":{}}' > "$STATE_FILE"
  fi
}

load_state() {
  if [[ -f "$STATE_FILE" ]]; then
    cat "$STATE_FILE"
  else
    echo '{"reviewed":{}}'
  fi
}

is_reviewed() {
  local owner_repo="$1"
  local pr_number="$2"
  local sha="$3"
  
  local state
  state=$(load_state)
  
  python3 -c "
import sys, json
try:
    d = json.loads('${state}')
except:
    print('false')
    sys.exit(0)

key = '${owner_repo}/${pr_number}'
entry = d.get('reviewed', {}).get(key, {})
if entry.get('sha') == '${sha}':
    print('true')
else:
    print('false')
" 2>/dev/null || echo "false"
}

get_repos() {
  if [[ -n "$REPOS_FILTER" ]]; then
    echo "$REPOS_FILTER"
    return
  fi
  
  if [[ -z "$FORGEJO_TOKEN" ]]; then
    echo "ERROR: FORGEJO_TOKEN required for listing repos" >&2
    return
  fi
  
  curl -sf -H "Authorization: token ${FORGEJO_TOKEN}" \
    "https://codeberg.org/api/v1/user/repos?limit=50" \
    | python3 -c "
import sys, json
data = json.load(sys.stdin)
for r in data:
    print(r['full_name'])
" 2>/dev/null || true
}

get_open_prs() {
  local repo="$1"
  
  curl -sf -H "Authorization: token ${FORGEJO_TOKEN}" \
    "https://codeberg.org/api/v1/repos/${repo}/pulls?state=open&limit=20" \
    | python3 -c "
import sys, json
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
" 2>/dev/null || true
}

get_diff() {
  local repo="$1"
  local pr_number="$2"
  
  curl -sf -H "Authorization: token ${FORGEJO_TOKEN}" \
    "https://codeberg.org/api/v1/repos/${repo}/pulls/${pr_number}.diff" 2>/dev/null || true
}

process_pr() {
  local repo="$1"
  local pr_number="$2"
  local pr_sha="$3"
  local pr_title="$4"
  
  echo "  PR #${pr_number}: ${pr_title:0:50}..."
  
  if [[ "$(is_reviewed "$repo" "$pr_number" "$pr_sha")" == "true" ]]; then
    echo "    -> already reviewed (SHA: ${pr_sha:0:7})"
    return 0
  fi
  
  echo "    -> NEW/UPDATED, analyzing..."
  
  if ! ollama_available; then
    echo "    -> ERROR: Ollama not available"
    return 1
  fi
  
  local diff
  diff=$(get_diff "$repo" "$pr_number")
  
  if [[ -z "$diff" ]] || [[ ${#diff} -lt 50 ]]; then
    echo "    -> SKIP: No diff available"
    return 0
  fi
  
  echo "    -> Sending to Ollama (model: ${OLLAMA_MODEL})..."
  
  local review_prompt
  review_prompt=$(DIFF_CONTENT="$diff" python3 "${SCRIPT_DIR}/lib/build-prompt.py")
  
  local ollama_host
  ollama_host=$(resolve_ollama_host)
  
  local response
  response=$(python3 -c "
import json
import os
import sys

data = {
    'model': os.environ.get('OLLAMA_MODEL', 'code-review'),
    'prompt': sys.stdin.read(),
    'stream': False
}
print(json.dumps(data))
" <<< "$review_prompt" | curl -sf -X POST "${ollama_host}/api/generate" \
    -H "Content-Type: application/json" \
    -d @- 2>&1) || {
      echo "    -> ERROR: Ollama request failed"
      return 1
    }
  
  local review
  review=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('response',''))" 2>/dev/null || true)
  
  if [[ -z "$review" ]]; then
    echo "    -> ERROR: No review from Ollama"
    return 1
  fi
  
  echo "    -> Posting review to Codeberg..."
  
  local api_token="${FORGEJO_TOKEN:-}"
  if [[ -z "$api_token" ]]; then
    echo "    -> ERROR: No API token"
    return 1
  fi
  
  local verdict comment_body build_output
  build_output=$(REVIEW_JSON="$review" OLLAMA_MODEL="$OLLAMA_MODEL" python3 "${SCRIPT_DIR}/lib/build-comment.py")
  verdict=$(echo "$build_output" | head -1)
  comment_body=$(echo "$build_output" | tail -n +2)
  
  echo "    -> Verdict: ${verdict}"

  # Post formal review using reviewer token (not comment)
  local escaped_body
  escaped_body=$(echo "$comment_body" | python3 "${SCRIPT_DIR}/lib/json-escape.py")

  local reviewer_token="${FORGEJO_REVIEWER_TOKEN:-}"
  local reviewer_username="${FORGEJO_REVIEWER_USERNAME:-}"

  if [[ -z "$reviewer_token" ]]; then
    echo "    -> ERROR: FORGEJO_REVIEWER_TOKEN not set"
    return 1
  fi

  if [[ -z "$reviewer_username" ]]; then
    echo "    -> ERROR: FORGEJO_REVIEWER_USERNAME not set"
    return 1
  fi

  # Convert verdict to event
  local event
  case "$verdict" in
    approved) event="APPROVED" ;;
    changes_requested) event="REQUEST_CHANGES" ;;
    *) event="COMMENT" ;;
  esac

  # Request reviewer using owner token
  local request_result
  request_result=$(curl -sf -X POST "${API_BASE}/repos/${repo}/pulls/${pr_number}/requested_reviewers" \
    -H "Authorization: token $api_token" \
    -H "Content-Type: application/json" \
    -d "{\"reviewers\":[\"$reviewer_username\"]}" 2>&1) || true

  # Post formal review using reviewer token
  local review_result
  review_result=$(curl -sf -X POST "${API_BASE}/repos/${repo}/pulls/${pr_number}/reviews" \
    -H "Authorization: token $reviewer_token" \
    -H "accept: application/json" \
    -H "Content-Type: application/json" \
    -d "{\"event\":\"${event}\",\"body\":${escaped_body}}" 2>&1) || true

  local review_id
  review_id=$(echo "$review_result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || true)

  if [[ -n "$review_id" ]] && [[ "$review_id" != "" ]]; then
    echo "    -> Review (${verdict}) submitted!"
  else
    echo "    -> ERROR: Failed to submit formal review: $review_result"
    return 1
  fi

  local state
  state=$(load_state)
  STATE_JSON="$state" REPO="$repo" PR_NUMBER="$pr_number" PR_SHA="$pr_sha" python3 -c "
import os, json
state = json.loads(os.environ.get('STATE_JSON', '{}'))
repo = os.environ.get('REPO', '')
pr_num = os.environ.get('PR_NUMBER', '')
pr_sha = os.environ.get('PR_SHA', '')
key = f'{repo}/{pr_num}'
if 'reviewed' not in state:
    state['reviewed'] = {}
state['reviewed'][key] = {'sha': pr_sha}
print(json.dumps(state))
" > "$STATE_FILE"

  echo "    -> State updated"
  return 0
}

cycle() {
  local cycle_num="$1"
  echo ""
  echo "=== Cycle #${cycle_num} ==="
  
  local repos
  repos=$(get_repos)
  
  if [[ -z "$repos" ]]; then
    echo "No repos found"
    return
  fi
  
  local repo_count
  repo_count=$(echo "$repos" | wc -l)
  echo "Watching ${repo_count} repo(s)"
  
  echo "$repos" | while read -r repo; do
    [[ -z "$repo" ]] && continue
    
    echo ""
    echo "Repo: $repo"
    
    local prs
    prs=$(get_open_prs "$repo")
    
    if [[ -z "$prs" ]]; then
      echo "  No open PRs"
      continue
    fi
    
    echo "$prs" | while IFS='|' read -r pr_number pr_sha pr_title; do
      process_pr "$repo" "$pr_number" "$pr_sha" "$pr_title" || true
    done
  done
}

init_state

if ! ollama_available; then
  echo "WARNING: Ollama not available. PR reviews will fail."
fi

echo "==> AI PR Review Watcher (Codeberg)"
echo "    Interval: ${INTERVAL}s"
echo "    Repos: ${REPOS_FILTER:-all}"
echo "    Ollama: $(resolve_ollama_host)"
echo "    Model: ${OLLAMA_MODEL}"
echo "    Hot-reload: ENABLED (edit .env to reload)"
echo "    Ctrl+C to stop"

cycle_num=0

while true; do
  cycle_num=$((cycle_num + 1))
  cycle "$cycle_num" || true
  
  if [[ "$RUN_ONCE" == true ]]; then
    break
  fi
  
  interruptible_sleep "$INTERVAL"
done
