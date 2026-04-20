#!/usr/bin/env bash
# validate-pr.sh — Fetch a PR from Codeberg and generate a local code review.
#
# Fetches the diff and repo structure from Codeberg, sends to Ollama,
# and outputs the review to stdout or file.
#
# Usage:
#   ./validate-pr.sh -r <repo> -p <pr-number> [-o <output-file>]
#
# Options:
#   -r <repo>      Repository in format owner/repo (required)
#   -p <pr>       PR number (required)
#   -o <path>     Write review to file instead of stdout
#   -b <branch>   Branch to use for repo structure (default: main)
#   -h            Show help

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

REPO=""
PR_NUMBER=""
OUTPUT_FILE=""
BRANCH="main"
SHOW_HELP=false

usage() {
  cat <<EOF
Usage: $(basename "$0") -r <repo> -p <pr-number> [-o <output-file>]

Fetch a PR from Codeberg and generate a local code review using Ollama.
The review includes both the diff and the repo file structure for context.

Options:
  -r <repo>      Repository in format owner/repo (required)
  -p <pr>        PR number (required)
  -o <path>      Write review to file instead of stdout
  -b <branch>    Branch to use for repo structure (default: main)
  -h             Show this help

Environment:
  FORGEJO_TOKEN     Codeberg API token (required)
  OLLAMA_HOST       Ollama endpoint (default: http://localhost:11434)
  OLLAMA_MODEL      Model to use (default: code-review)

Examples:
  $(basename "$0") -r owner/repo -p 42
  $(basename "$0") -r owner/repo -p 42 -o review.md
  $(basename "$0") -r owner/repo -p 42 -b develop
EOF
  exit 0
}

while getopts "r:p:o:b:h" opt; do
  case "$opt" in
    r) REPO="$OPTARG" ;;
    p) PR_NUMBER="$OPTARG" ;;
    o) OUTPUT_FILE="$OPTARG" ;;
    b) BRANCH="$OPTARG" ;;
    h) SHOW_HELP=true ;;
    *) usage ;;
  esac
done

if [[ "$SHOW_HELP" == "true" ]]; then
  usage
fi

if [[ -z "$REPO" ]]; then
  echo "ERROR: -r <repo> is required" >&2
  usage
fi

if [[ -z "$PR_NUMBER" ]]; then
  echo "ERROR: -p <pr-number> is required" >&2
  usage
fi

source "${SCRIPT_DIR}/lib/config-loader.sh"
load_config

source "${SCRIPT_DIR}/lib/forgejo-api.sh"
source "${SCRIPT_DIR}/lib/ollama-client.sh"

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-code-review:latest}"

if [[ -z "${FORGEJO_TOKEN:-}" ]]; then
  echo "ERROR: FORGEJO_TOKEN is required" >&2
  exit 1
fi

if ! ollama_available; then
  echo "ERROR: Ollama not available at ${OLLAMA_HOST}" >&2
  echo "Make sure Ollama is running and the model '${OLLAMA_MODEL}' is available." >&2
  exit 1
fi

echo "Fetching PR #${PR_NUMBER} from ${REPO}..." >&2

diff_content=$(forgejo_get_pr_diff "$REPO" "$PR_NUMBER")

if [[ -z "$diff_content" ]]; then
  echo "ERROR: Failed to fetch diff for PR #${PR_NUMBER}" >&2
  exit 1
fi

if [[ ${#diff_content} -lt 50 ]]; then
  echo "ERROR: Diff content too short (${#diff_content} bytes)" >&2
  exit 1
fi

echo "Fetching repo structure from branch '${BRANCH}'..." >&2

repo_structure=$(forgejo_get_repo_tree "$REPO" "$BRANCH" 2>/dev/null || true)

if [[ -z "$repo_structure" ]]; then
  echo "WARNING: Could not fetch repo structure, continuing without it..." >&2
fi

echo "Generating review..." >&2
echo "  Repo: ${REPO}" >&2
echo "  PR: #${PR_NUMBER}" >&2
echo "  Diff: ${#diff_content} bytes" >&2
if [[ -n "$repo_structure" ]]; then
  echo "  Repo structure: ${#repo_structure} bytes" >&2
fi
echo "  Model: ${OLLAMA_MODEL}" >&2

review_prompt=$(DIFF_CONTENT="$diff_content" REPO_STRUCTURE="$repo_structure" python3 "${SCRIPT_DIR}/lib/build_prompt.py")

ollama_host=$(resolve_ollama_host)

if [[ -z "$ollama_host" ]]; then
  echo "ERROR: Ollama host not resolved" >&2
  exit 1
fi

response_file=$(mktemp)
curl_err=$(mktemp)

set +e
http_status=$(
  python3 -c "
import json
import os
import sys

data = {
    'model': os.environ.get('OLLAMA_MODEL', 'code-review'),
    'prompt': sys.stdin.read(),
    'stream': False
}
print(json.dumps(data))
" <<< "$review_prompt" | curl -sS -X POST "${ollama_host}/api/generate" \
    -H "Content-Type: application/json" \
    -d @- \
    -o "$response_file" \
    -w "%{http_code}" 2>"$curl_err"
)
curl_exit=$?
set -e

if [[ $curl_exit -ne 0 ]] || ! [[ "$http_status" =~ ^2[0-9][0-9]$ ]]; then
  curl_details=$(tr '\n' ' ' < "$curl_err" | sed 's/[[:space:]]\+/ /g; s/^ //; s/ $//')
  response_excerpt=$(tr '\n' ' ' < "$response_file" | sed 's/[[:space:]]\+/ /g; s/^ //; s/ $//' | cut -c1-240)
  echo "ERROR: Ollama request failed (host: ${ollama_host}, model: ${OLLAMA_MODEL}, http: ${http_status:-unknown}, curl exit: ${curl_exit})" >&2
  if [[ -n "$curl_details" ]]; then
    echo "  curl: ${curl_details}" >&2
  fi
  if [[ -n "$response_excerpt" ]]; then
    echo "  body: ${response_excerpt}" >&2
  fi
  rm -f "$response_file" "$curl_err"
  exit 1
fi

response=$(cat "$response_file")
rm -f "$response_file" "$curl_err"

review=$(echo "$response" | python3 -c "import sys,json; print(json.load(sys.stdin).get('response',''))" 2>/dev/null || true)

if [[ -z "$review" ]]; then
  echo "ERROR: No review generated from Ollama" >&2
  exit 1
fi

build_output=$(REVIEW_JSON="$review" OLLAMA_MODEL="$OLLAMA_MODEL" python3 "${SCRIPT_DIR}/lib/build_comment.py")
verdict=$(echo "$build_output" | head -1)
comment_body=$(echo "$build_output" | tail -n +2)

output="VERDICT: ${verdict}

${comment_body}"

if [[ -n "$OUTPUT_FILE" ]]; then
  echo "$output" > "$OUTPUT_FILE"
  echo "Review written to: ${OUTPUT_FILE}" >&2
else
  echo "$output"
fi