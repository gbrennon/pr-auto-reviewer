#!/usr/bin/env bash
# validate.sh — Generate a local code review from a diff file using Ollama.
#
# No Codeberg API calls — review is printed to stdout or written to a file.
# Optionally includes repo structure for architectural context.
#
# Usage:
#   ./validate.sh -d <diff-file> [-o <output-file>] [-r <repo-path>]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

DIFF_FILE=""
OUTPUT_FILE=""
REPO_PATH=""
SHOW_HELP=false

usage() {
  cat <<EOF
Usage: $(basename "$0") -d <diff-file> [-o <output-file>] [-r <repo-path>]

Generate a local code review from a diff file using Ollama.
No Codeberg API calls -- review is printed to stdout or written to a file.

Options:
  -d <path>   Path to diff/patch file (required)
  -o <path>   Write review to file instead of stdout
  -r <path>   Local repo path to include file tree structure in review
  -h          Show this help

Environment:
  OLLAMA_HOST       Ollama endpoint (default: http://localhost:11434)
  OLLAMA_MODEL      Model to use (default: code-review)

Examples:
  $(basename "$0") -d changes.patch
  $(basename "$0") -d changes.patch -o review.md
  $(basename "$0") -d changes.patch -r /path/to/my-repo
EOF
  exit 0
}

while getopts "d:o:r:h" opt; do
  case "$opt" in
    d) DIFF_FILE="$OPTARG" ;;
    o) OUTPUT_FILE="$OPTARG" ;;
    r) REPO_PATH="$OPTARG" ;;
    h) SHOW_HELP=true ;;
    *) usage ;;
  esac
done

if [[ "$SHOW_HELP" == "true" ]]; then
  usage
fi

if [[ -z "$DIFF_FILE" ]]; then
  echo "ERROR: -d <diff-file> is required" >&2
  usage
fi

if [[ ! -f "$DIFF_FILE" ]]; then
  echo "ERROR: diff file not found: $DIFF_FILE" >&2
  exit 1
fi

if [[ -n "$REPO_PATH" ]] && [[ ! -d "$REPO_PATH" ]]; then
  echo "ERROR: repo path not found: $REPO_PATH" >&2
  exit 1
fi

source "${SCRIPT_DIR}/lib/config-loader.sh"
load_config

source "${SCRIPT_DIR}/lib/ollama-client.sh"

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-code-review:latest}"

if ! ollama_available; then
  echo "ERROR: Ollama not available at ${OLLAMA_HOST}" >&2
  echo "Make sure Ollama is running and the model '${OLLAMA_MODEL}' is available." >&2
  exit 1
fi

diff_content=$(cat "$DIFF_FILE")

if [[ -z "$diff_content" ]]; then
  echo "ERROR: diff file is empty: $DIFF_FILE" >&2
  exit 1
fi

if [[ ${#diff_content} -lt 50 ]]; then
  echo "ERROR: diff content too short (${#diff_content} bytes). Minimum 50 bytes required." >&2
  exit 1
fi

architecture_hint=""
repo_structure=""
conventions=""

if [[ -n "$REPO_PATH" ]]; then
  echo "  Generating repo structure from: ${REPO_PATH}" >&2
  repo_structure=$(python3 "${SCRIPT_DIR}/lib/generate_repo_structure.py" "$REPO_PATH" 2>/dev/null || true)
  architecture_hint=$(python3 "${SCRIPT_DIR}/lib/generate_repo_structure.py" --detect-type "$REPO_PATH" 2>/dev/null || echo "unknown")

  for conf_file in ARCHITECTURE.md CONVENTIONS.md .architecturerc; do
    if [[ -f "${REPO_PATH}/${conf_file}" ]]; then
      conventions=$(cat "${REPO_PATH}/${conf_file}")
      echo "  Conventions: ${conf_file} (${#conventions} bytes)" >&2
      break
    fi
  done
fi

echo "Generating review..." >&2
echo "  Diff: ${DIFF_FILE} (${#diff_content} bytes)" >&2
echo "  Model: ${OLLAMA_MODEL}" >&2
if [[ -n "$architecture_hint" ]] && [[ "$architecture_hint" != "unknown" ]]; then
  echo "  Project type: ${architecture_hint}" >&2
fi
if [[ -n "$repo_structure" ]]; then
  echo "  Repo structure: included (${#repo_structure} bytes)" >&2
fi

review_prompt=$(DIFF_CONTENT="$diff_content" REPO_STRUCTURE="$repo_structure" ARCHITECTURE_HINT="$architecture_hint" CONVENTIONS="$conventions" python3 "${SCRIPT_DIR}/lib/build_prompt.py")

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