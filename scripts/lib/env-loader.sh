#!/usr/bin/env bash
# env-loader.sh — Load and validate environment variables from .env

set -euo pipefail

load_env() {
  if [[ -z "${REPO_ROOT:-}" ]]; then
    echo "ERROR: REPO_ROOT not set" >&2
    return 1
  fi

  if [[ ! -f "${REPO_ROOT}/.env" ]]; then
    return 1
  fi

  set -a
  source "${REPO_ROOT}/.env"
  set +a
}

require_env() {
  local var_name="$1"
  local var_value="${!var_name:-}"

  if [[ -z "$var_value" ]]; then
    echo "ERROR: $var_name is not set" >&2
    return 1
  fi

  return 0
}

get_env() {
  local var_name="$1"
  local default="$2"
  echo "${!var_name:-$default}"
}

init_env() {
  load_env

  export CODEBERG_TOKEN="${CODEBERG_TOKEN:-}"
  export GITHUB_PAT="${GITHUB_PAT:-}"
  export OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
  export OLLAMA_MODEL="${OLLAMA_MODEL:-code-review}"
  export POLL_INTERVAL="${POLL_INTERVAL:-60}"
}
