#!/usr/bin/env bash
# hot-reload.sh — Shared library for hot-reloading configuration via SIGHUP or automatic file watching.

set -euo pipefail

RELOAD_REQUESTED=false
REPO_ROOT_PATH=""
CONFIG_SNAPSHOT=""
CONFIG_FILE=""
REPO_ENV=""
LAST_CONFIG_MTIME=""

get_config_mtime() {
    if [[ -f "$CONFIG_FILE" ]]; then
        stat --format=%Y "$CONFIG_FILE" 2>/dev/null || echo "0"
    elif [[ -f "$REPO_ENV" ]]; then
        stat --format=%Y "$REPO_ENV" 2>/dev/null || echo "0"
    else
        echo "0"
    fi
}

check_config_changed() {
    local current_mtime
    current_mtime=$(get_config_mtime)
    
    if [[ -z "$LAST_CONFIG_MTIME" ]]; then
        LAST_CONFIG_MTIME="$current_mtime"
        return 1
    fi
    
    [[ "$current_mtime" != "$LAST_CONFIG_MTIME" ]]
}

load_config_file() {
    if [[ -f "$CONFIG_FILE" ]]; then
        set -a
        source "$CONFIG_FILE" 2>/dev/null || true
        set +a
        return 0
    fi
    
    if [[ -f "$REPO_ENV" ]]; then
        set -a
        source "$REPO_ENV" 2>/dev/null || true
        return 0
    fi
    
    return 1
}

init_hot_reload() {
    local repo_root="$1"
    REPO_ROOT_PATH="$(cd "$repo_root" && pwd)"
    CONFIG_FILE="${HOME}/.config/pr-auto-reviewer/config"
    REPO_ENV="${REPO_ROOT_PATH}/.env"
    
    load_config_file
    
    CONFIG_SNAPSHOT="$(capture_config_snapshot)"
    LAST_CONFIG_MTIME=$(get_config_mtime)
    
    trap 'handle_sighup' HUP
    
    echo "[hot-reload] Initialized. Send SIGHUP or edit config to reload."
    echo "[hot-reload] Initial config: $(echo "$CONFIG_SNAPSHOT" | head -1)"
}

handle_sighup() {
    RELOAD_REQUESTED=true
}

reload_config() {
    echo "[hot-reload] Reloading configuration..."
    
    local old_model="$OLLAMA_MODEL"
    local old_host="$OLLAMA_HOST"
    local old_interval="$INTERVAL"
    local old_forgejo="$FORGEJO_HOST"
    
    load_config_file || echo "[hot-reload] WARNING: No config file found"
    
    FORGEJO_HOST="${FORGEJO_HOST:-https://codeberg.org}"
    OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
    OLLAMA_MODEL="${OLLAMA_MODEL:-code-review}"
    INTERVAL="${INTERVAL:-${POLL_INTERVAL:-60}}"
    
    echo "[hot-reload] Configuration reloaded:"
    [[ "$old_model" != "$OLLAMA_MODEL" ]] && echo "  OLLAMA_MODEL: ${old_model:-<unset>} -> $OLLAMA_MODEL"
    [[ "$old_host" != "$OLLAMA_HOST" ]] && echo "  OLLAMA_HOST: ${old_host:-<unset>} -> $OLLAMA_HOST"
    [[ "$old_interval" != "$INTERVAL" ]] && echo "  INTERVAL: ${old_interval:-60} -> $INTERVAL"
    [[ "$old_forgejo" != "$FORGEJO_HOST" ]] && echo "  FORGEJO_HOST: ${old_forgejo:-<unset>} -> $FORGEJO_HOST"
    
    CONFIG_SNAPSHOT="$(capture_config_snapshot)"
    RELOAD_REQUESTED=false
    
    echo "[hot-reload] Reload complete."
}

capture_config_snapshot() {
    echo "OLLAMA_MODEL=${OLLAMA_MODEL:-},OLLAMA_HOST=${OLLAMA_HOST:-},INTERVAL=${INTERVAL:-60},FORGEJO_HOST=${FORGEJO_HOST:-}"
}

interruptible_sleep() {
    local interval="$1"
    local count=0
    
    while [[ $count -lt $interval ]]; do
        sleep 1
        ((count++)) || true
        
        if [[ "$RELOAD_REQUESTED" == "true" ]]; then
            reload_config
            count=0
        elif check_config_changed; then
            reload_config
            count=0
        fi
    done
}

apply_hot_reload() {
    if [[ "$RELOAD_REQUESTED" == "true" ]]; then
        reload_config
    elif check_config_changed; then
        reload_config
    fi
}