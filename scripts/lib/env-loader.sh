#!/usr/bin/env bash
# env-loader.sh — Load and validate environment variables from config

set -euo pipefail

load_env() {
    CONFIG_FILE="${HOME}/.config/pr-auto-reviewer/config"
    REPO_ENV="${REPO_ROOT:-.}/.env"
    
    if [[ -f "$CONFIG_FILE" ]]; then
        set -a
        source "$CONFIG_FILE"
        set +a
        return 0
    fi
    
    if [[ -f "$REPO_ENV" ]]; then
        set -a
        source "$REPO_ENV"
        set +a
        return 0
    fi
    
    echo "ERROR: No config file found at $CONFIG_FILE or $REPO_ENV" >&2
    return 1
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
    load_env || true

    export OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
    export OLLAMA_MODEL="${OLLAMA_MODEL:-code-review}"
    export POLL_INTERVAL="${POLL_INTERVAL:-60}"
}