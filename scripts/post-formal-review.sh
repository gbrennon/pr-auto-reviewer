#!/usr/bin/env bash

set -euo pipefail
trap 'echo "[ERROR] Script failed at line $LINENO" >&2' ERR

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DEBUG="${DEBUG:-0}"

log() {
  echo "[INFO] $(date '+%H:%M:%S') $1" >&2
}

log_debug() {
  if [[ "$DEBUG" == "1" ]]; then
    echo "[DEBUG] $(date '+%H:%M:%S') $1" >&2
  fi
}

fail() {
  echo "[ERROR] $1" >&2
  exit 1
}

load_environment_variables() {
  local env_file="${REPO_ROOT}/.env"

  if [[ ! -f "$env_file" ]]; then
    log ".env not found"
    return
  fi

  log "Loading .env from $env_file"

  set +euo pipefail
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" || "$line" =~ ^# ]] && continue
    if ! export "$line" 2>/dev/null; then
      continue
    fi
  done < "$env_file"
  set -euo pipefail
}

validate_command_arguments() {
  if [[ $# -lt 2 ]]; then
    fail "Usage: $(basename "$0") <repo> <pr_number>"
  fi
}

validate_repo_and_pr() {
  local repo="$1"
  local pr="$2"
  local api_base="$3"
  local token="$4"

  local repo_response
  repo_response=$(curl -sf -H "Authorization: token ${token}" \
    "${api_base}/repos/${repo}" 2>/dev/null) || {
    fail "Repository '${repo}' not found or not accessible"
  }

  local pr_response
  pr_response=$(curl -sf -H "Authorization: token ${token}" \
    "${api_base}/repos/${repo}/pulls/${pr}" 2>/dev/null) || {
    fail "PR #${pr} not found in repository '${repo}'"
  }

  log "Repository: ${repo}"
  log "PR #${pr} validated"
}

get_forgejo_api_base_url() {
  if [[ "${FORGEJO_MODE:-}" == "local" ]]; then
    echo "http://forgejo.local/api/v1"
  else
    echo "${FORGEJO_HOST:-https://codeberg.org}/api/v1"
  fi
}

get_repository_owner_token() {
  echo "${FORGEJO_TOKEN:-}"
}

get_reviewer_token() {
  echo "${FORGEJO_REVIEWER_TOKEN:-}"
}

get_reviewer_login_from_token() {
  local token="$1"
  local api_base
  api_base=$(get_forgejo_api_base_url)

  curl -sf -H "Authorization: token ${token}" "${api_base}/user" 2>/dev/null | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('login',''))" 2>/dev/null || echo ""
}

resolve_ollama_endpoint() {
  if curl -s "http://localhost:11434/api/tags" >/dev/null 2>&1; then
    echo "http://localhost:11434"
    return
  fi

  if [[ -n "${OLLAMA_HOST:-}" ]] && curl -s "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
    echo "$OLLAMA_HOST"
    return
  fi

  fail "Ollama not reachable"
}

fetch_pull_request_diff() {
  local repo="$1"
  local pr="$2"
  local api_base
  api_base=$(get_forgejo_api_base_url)

  log "Fetching PR diff from: ${api_base}/repos/${repo}/pulls/${pr}.diff"
  curl -s "${api_base}/repos/${repo}/pulls/${pr}.diff"
}

fetch_pull_request_author() {
  local repo="$1"
  local pr="$2"
  local api_base
  api_base=$(get_forgejo_api_base_url)

  curl -s "${api_base}/repos/${repo}/pulls/${pr}" | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('user',{}).get('login',''))"
}

send_diff_to_ollama_for_review() {
  local diff="$1"
  local ollama_host="$2"
  local model="$3"

  log "Building Ollama prompt..."
  local prompt
  prompt=$(DIFF_CONTENT="$diff" python3 -c "$(cat "${REPO_ROOT}/scripts/lib/build-prompt.py" | tail -n +2)")

  log "Sending to Ollama: POST ${ollama_host}/api/generate"
  log "  Model: $model, Prompt length: ${#prompt}"

  local response
  response=$(curl -sf -X POST "${ollama_host}/api/generate" \
    -H "Content-Type: application/json" \
    -d "{
      \"model\": \"${model}\",
      \"prompt\": $(printf '%s' "$prompt" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))'),
      \"stream\": false
    }")

  echo "$response" | python3 -c 'import sys,json; print(json.load(sys.stdin).get("response",""))'
}

parse_ollama_response_into_review_output() {
  local review_json="$1"
  local model="$2"

  REVIEW_JSON="$review_json" OLLAMA_MODEL="$model" python3 -c "$(cat "${REPO_ROOT}/scripts/lib/build-comment.py" | tail -n +2)"
}

extract_verdict_from_review_output() {
  local review_output="$1"
  echo "$review_output" | head -1
}

extract_review_body_from_output() {
  local review_output="$1"
  echo "$review_output" | tail -n +2
}

map_verdict_to_review_event() {
  local verdict="$1"
  case "$verdict" in
    approved)           echo "APPROVED" ;;
    changes_requested)  echo "REQUEST_CHANGES" ;;
    *)                  echo "COMMENT" ;;
  esac
}

request_reviewer_for_pull_request() {
  local repo="$1"
  local pr="$2"
  local reviewer_login="$3"
  local owner_token="$4"
  local api_base
  api_base=$(get_forgejo_api_base_url)

  local url="${api_base}/repos/${repo}/pulls/${pr}/requested_reviewers"
  log "Requesting reviewer: POST $url"
  log "  Reviewer: $reviewer_login"

  curl -sf -X POST "$url" \
    -H "Authorization: token ${owner_token}" \
    -H "Content-Type: application/json" \
    -d "{\"reviewers\":[\"$reviewer_login\"]}" >/dev/null 2>&1 || true
}

delete_stale_pending_reviews() {
  local repo="$1"
  local pr="$2"
  local reviewer_login="$3"
  local reviewer_token="$4"
  local api_base
  api_base=$(get_forgejo_api_base_url)

  log "Cleaning stale reviews for: $reviewer_login"

  local stale_ids
  stale_ids=$(curl -sf "${api_base}/repos/${repo}/pulls/${pr}/reviews" \
    -H "Authorization: token ${reviewer_token}" \
    2>/dev/null | python3 -c "
import sys, json
reviews = json.load(sys.stdin)
for r in reviews:
    if r.get('state') == 'PENDING' and r.get('user',{}).get('login') == '$reviewer_login':
        print(r['id'])
" 2>/dev/null || true)

  if [[ -n "$stale_ids" ]]; then
    while IFS= read -r stale_id; do
      [[ -z "$stale_id" ]] && continue
      log "  Deleting stale review: $stale_id"
      curl -sf -X DELETE \
        "${api_base}/repos/${repo}/pulls/${pr}/reviews/${stale_id}" \
        -H "Authorization: token ${reviewer_token}" >/dev/null 2>&1 || true
    done <<< "$stale_ids"
  fi
}

post_review_to_pull_request() {
  local repo="$1"
  local pr="$2"
  local event="$3"
  local body="$4"
  local reviewer_token="$5"
  local api_base
  api_base=$(get_forgejo_api_base_url)

  local body_escaped
  body_escaped=$(printf '%s' "$body" | python3 -c 'import json,sys; print(json.dumps(sys.stdin.read()))')

  local payload
  payload=$(python3 -c "import json; print(json.dumps({'event': '$event', 'body': $body_escaped, 'comments': []}))")

  local url="${api_base}/repos/${repo}/pulls/${pr}/reviews"
  log "Posting review: POST $url"
  log "  Event: $event"
  log "  Body length: ${#body}"
  log "  Payload: $payload"

  local http_code
  http_code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$url" \
    -H "Authorization: token ${reviewer_token}" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>&1)

  log "HTTP response code: $http_code"

  local result
  result=$(curl -sf -X POST "$url" \
    -H "Authorization: token ${reviewer_token}" \
    -H "Content-Type: application/json" \
    -d "$payload" 2>&1)

  log "Curl result: $result"

  if [[ "$http_code" -ne 200 && "$http_code" -ne 201 ]]; then
    log "ERROR: Failed to post review - HTTP $http_code: $result"
    result=$(echo "$result" | python3 -c "import sys,re; d=sys.stdin.read(); m=re.search(r'\{.*\}', d, re.DOTALL); print(m.group(0) if m else '{}')" 2>/dev/null || echo "{}")
  fi

  echo "$result"
}

execute_review_workflow() {
  local repo="$1"
  local pr="$2"
  local event="$3"
  local body="$4"
  local reviewer_token="$5"
  local owner_token="$6"
  local reviewer_login="$7"

  delete_stale_pending_reviews "$repo" "$pr" "$reviewer_login" "$reviewer_token"
  request_reviewer_for_pull_request "$repo" "$pr" "$reviewer_login" "$owner_token"
  post_review_to_pull_request "$repo" "$pr" "$event" "$body" "$reviewer_token"
}

main() {
  log "=== PR Auto Reviewer ==="
  log "DEBUG: $DEBUG"
  log "FORGEJO_MODE: ${FORGEJO_MODE:-not set}"

  load_environment_variables
  log "Environment loaded"

  validate_command_arguments "$@"

  local repo="$1"
  local pr="$2"

  local api_base owner_token
  api_base=$(get_forgejo_api_base_url)
  owner_token=$(get_repository_owner_token)

  validate_repo_and_pr "$repo" "$pr" "$api_base" "$owner_token"

  log "Processing: $repo PR #$pr"

  local diff
  diff=$(fetch_pull_request_diff "$repo" "$pr")

  if [[ -z "$diff" || ${#diff} -lt 50 ]]; then
    fail "No diff available for PR #$pr"
  fi

  local ollama_host
  ollama_host=$(resolve_ollama_endpoint)
  log "Ollama endpoint: $ollama_host"

  local model
  model="${OLLAMA_MODEL:-code-review}"
  log "Ollama model: $model"

  local author
  author=$(fetch_pull_request_author "$repo" "$pr")
  log "PR author: $author"

  log "Running Ollama review..."
  local review_json
  review_json=$(send_diff_to_ollama_for_review "$diff" "$ollama_host" "$model")

  if [[ -z "$review_json" ]]; then
    fail "Ollama returned empty response"
  fi

  log "Parsing Ollama response..."
  local review_output
  review_output=$(parse_ollama_response_into_review_output "$review_json" "$model")

  local verdict
  verdict=$(extract_verdict_from_review_output "$review_output")
  log "Ollama verdict: $verdict"

  local event
  event=$(map_verdict_to_review_event "$verdict")
  log "Review event: $event"

  local body
  body=$(extract_review_body_from_output "$review_output")

  local owner_token
  owner_token=$(get_repository_owner_token)
  log "Owner token: ${owner_token:0:8}..."

  local reviewer_token
  reviewer_token=$(get_reviewer_token)
  log "Reviewer token: ${reviewer_token:0:8}..."

  local reviewer_login
  reviewer_login=$(get_reviewer_login_from_token "$reviewer_token")
  if [[ -z "$reviewer_login" && -n "${FORGEJO_REVIEWER_USERNAME:-}" ]]; then
    reviewer_login="${FORGEJO_REVIEWER_USERNAME}"
    log "Using reviewer username from env: $reviewer_login"
  fi
  log "Reviewer login: $reviewer_login"

  if [[ -z "$reviewer_login" ]]; then
    fail "Invalid reviewer token - cannot determine reviewer login"
  fi

  if [[ "$reviewer_login" == "$author" ]]; then
    fail "Self-review detected - reviewer cannot be the same as PR author"
  fi

  log "Executing review workflow..."
  local result
  result=$(execute_review_workflow "$repo" "$pr" "$event" "$body" "$reviewer_token" "$owner_token" "$reviewer_login")

  local review_id
  review_id=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")

  if [[ -n "$review_id" ]]; then
    local state
    state=$(echo "$result" | python3 -c "import sys,json; print(json.load(sys.stdin).get('state',''))" 2>/dev/null || echo "")
    log "Review posted successfully!"
    log "  Review ID: $review_id"
    log "  State: $state"
  else
    log "Review response: $result"
    fail "Failed to post review"
  fi
}

main "$@"