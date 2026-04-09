#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

WATCHER_LOCK_FILE="${REPO_ROOT}/watcher-prs.lock"
WATCHER_PID_FILE="${REPO_ROOT}/watcher-prs.pid"

exec 9>"$WATCHER_LOCK_FILE"
if ! flock -n 9; then
  echo "watch-prs.sh is already running. Exiting." >&2
  exit 1
fi

echo $$ > "$WATCHER_PID_FILE"
trap 'rm -f "$WATCHER_PID_FILE"' EXIT INT TERM

source "${SCRIPT_DIR}/lib/hot-reload.sh"

source "${REPO_ROOT}/.env" 2>/dev/null || true

FORGEJO_TOKEN="${FORGEJO_TOKEN:-}"

if [[ "${FORGEJO_MODE:-codeberg}" == "local" ]]; then
  FORGEJO_HOST="${FORGEJO_HOST:-http://forgejo.local}"
else
  FORGEJO_HOST="${FORGEJO_HOST:-https://codeberg.org}"
fi

API_BASE="${FORGEJO_HOST}/api/v1"
DEBUG="${DEBUG:-0}"
INTERVAL="${POLL_INTERVAL:-60}"
REPOS_FILTER=""
RUN_ONCE=false
STATE_FILE="${REPO_ROOT}/runner-data/pr-reviews.json"

source "${SCRIPT_DIR}/lib/ollama-client.sh"

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-code-review}"

init_hot_reload "$REPO_ROOT"

while [[ $# -gt 0 ]]; do
  case "$1" in
    -i) INTERVAL="$2"; shift 2 ;;
    -r) REPOS_FILTER="$2"; shift 2 ;;
    --once) RUN_ONCE=true; shift ;;
    *) echo "Unknown: $1" >&2; exit 1 ;;
  esac
done

debug_log() {
  if [[ "$DEBUG" == "1" ]]; then
    echo "[DEBUG] $(date '+%H:%M:%S') $1" >&2
  fi
}

init_state() {
  mkdir -p "$(dirname "$STATE_FILE")"
  [[ -f "$STATE_FILE" ]] || echo '{"reviewed":{}}' > "$STATE_FILE"
}

load_state() {
  cat "$STATE_FILE" 2>/dev/null || echo '{"reviewed":{}}'
}

is_reviewed() {
  local owner_repo="$1"
  local pr_number="$2"
  local sha="$3"

  local state
  state=$(load_state)

  python3 - <<EOF
import json
try:
    d = json.loads('''$state''')
    key = "$owner_repo/$pr_number"
    print("true" if d.get("reviewed", {}).get(key, {}).get("sha") == "$sha" else "false")
except:
    print("false")
EOF
}

get_repos() {
  [[ -n "$REPOS_FILTER" ]] && { echo "$REPOS_FILTER"; return; }

  local response
  response=$(curl -sf -H "Authorization: token ${FORGEJO_TOKEN}" \
    "${API_BASE}/user/repos?limit=50" 2>&1)

  if [[ -z "$response" ]]; then
    echo "  -> empty response from API" >&2
    return
  fi

  printf '%s' "$response" | python3 -c '
import sys, json
try:
    data = json.load(sys.stdin)
    for r in data:
        print(r["full_name"])
except Exception as e:
    sys.stderr.write(f"Error: {e}\n")
' || true
}

get_open_prs() {
  local repo="$1"

  local response
  response=$(curl -sf -H "Authorization: token ${FORGEJO_TOKEN}" \
    "${API_BASE}/repos/${repo}/pulls?state=open&limit=20" 2>/dev/null) || true

  if [[ -z "$response" ]]; then
    return
  fi

  python3 -c "
import sys, json
data = json.load(sys.stdin)
prs = data if isinstance(data, list) else data.get('data', [])
for pr in prs:
    if pr.get('draft'): continue
    print(f\"{pr['number']}|{pr['head']['sha']}|{pr['title']}\")
" <<< "$response" || true
}

get_diff() {
  curl -sf -H "Authorization: token ${FORGEJO_TOKEN}" \
    "${API_BASE}/repos/$1/pulls/$2.diff" || true
}

post_formal_review() {
  local repo="$1"
  local pr_number="$2"
  local event="$3"
  local escaped_body="$4"

  local body
  body=$(echo "$escaped_body" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read()))')

  "${REPO_ROOT}/post-formal-review.sh" \
    "$repo" \
    "$pr_number" \
    "$event" \
    "$body"
}

process_pr() {
  local repo="$1"
  local pr_number="$2"
  local pr_sha="$3"
  local pr_title="$4"

  echo "  PR #${pr_number}: ${pr_title:0:50}..."

  if [[ "$(is_reviewed "$repo" "$pr_number" "$pr_sha")" == "true" ]]; then
    echo "    -> already reviewed"
    return
  fi

  local diff
  diff=$(get_diff "$repo" "$pr_number")
  debug_log "Fetched diff: ${#diff} bytes"

  [[ -z "$diff" || ${#diff} -lt 50 ]] && {
    echo "    -> no diff"
    return
  }

  local prompt
  prompt=$(DIFF_CONTENT="$diff" python3 "${SCRIPT_DIR}/lib/build-prompt.py")
  debug_log "Built prompt: ${#prompt} chars"

  local payload
  payload=$(python3 -c "import json,sys; print(json.dumps({'model': '${OLLAMA_MODEL}', 'prompt': '''$prompt''', 'stream': False}))")
  debug_log "Ollama payload: model=${OLLAMA_MODEL}, prompt_len=${#prompt}"

  local start_time
  start_time=$(date +%s)

  local response
  response=$(curl -sf -X POST "$(resolve_ollama_host)/api/generate" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>&1) || {
    echo "    -> ollama failed (response: $response)" >&2
    return
  }

  local end_time
  end_time=$(date +%s)
  debug_log "Ollama response: ${#response} bytes in $((end_time - start_time))s"

  local review
  review=$(echo "$response" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("response",""))')
  debug_log "Extracted review: ${#review} chars"

  [[ -z "$review" ]] && { echo "    -> empty review"; return; }

  local build_output verdict body
  build_output=$(REVIEW_JSON="$review" python3 "${SCRIPT_DIR}/lib/build-comment.py")
  verdict=$(echo "$build_output" | head -1)
  body=$(echo "$build_output" | tail -n +2)

  local event
  case "$verdict" in
    approved) event="APPROVED" ;;
    changes_requested) event="REQUEST_CHANGES" ;;
    *) event="COMMENT" ;;
  esac
  debug_log "Verdict: $verdict -> Event: $event"

  local escaped
  escaped=$(echo "$body" | python3 "${SCRIPT_DIR}/lib/json-escape.py")

  debug_log "Posting formal review to ${API_BASE}/repos/${repo}/pulls/${pr_number}/reviews"
  local review_start
  review_start=$(date +%s)

  post_formal_review "$repo" "$pr_number" "$event" "$escaped"

  local review_end
  review_end=$(date +%s)
  debug_log "Formal review posted in $((review_end - review_start))s"

  echo "    -> review posted (verdict: $verdict)"

  local state
  state=$(load_state)

  STATE_JSON="$state" REPO="$repo" PR_NUMBER="$pr_number" PR_SHA="$pr_sha" \
  python3 - <<EOF > "$STATE_FILE"
import os,json
s=json.loads(os.environ["STATE_JSON"])
s.setdefault("reviewed",{})[f"{os.environ['REPO']}/{os.environ['PR_NUMBER']}"]={"sha":os.environ["PR_SHA"]}
print(json.dumps(s))
EOF
}

cycle() {
  get_repos | while read -r repo; do
    echo "Repo: $repo"
    get_open_prs "$repo" | while IFS='|' read -r n sha title; do
      process_pr "$repo" "$n" "$sha" "$title"
    done
  done
}

init_state

while true; do
  cycle
  [[ "$RUN_ONCE" == true ]] && break
  sleep "$INTERVAL"
done
