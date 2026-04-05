#!/usr/bin/env bash
# hot-reload.sh — Shared library for hot-reloading configuration via SIGHUP or automatic file watching.
#
# Usage:
#   source "${SCRIPT_DIR}/lib/hot-reload.sh"
#   init_hot_reload "$REPO_ROOT"
#   # In main loop, replace "sleep $INTERVAL" with:
#   interruptible_sleep "$INTERVAL"
#
# Features:
#   - SIGHUP signal triggers immediate reload
#   - Automatic .env file change detection (every 10 seconds)
#   - Variables are tracked: FORGEJO_HOST, OLLAMA_HOST, OLLAMA_MODEL, POLL_INTERVAL, etc.

set -euo pipefail

# Global state for hot-reload
RELOAD_REQUESTED=false
REPO_ROOT_PATH=""
CONFIG_SNAPSHOT=""
ENV_FILE=""
LAST_ENV_MTIME=""

# Get .env modification time
get_env_mtime() {
  if [[ -f "$ENV_FILE" ]]; then
    # Use stat with %Y for modification time
    stat --format=%Y "$ENV_FILE" 2>/dev/null || { echo "0"; return 1; }
  else
    echo "0"
    return 1
  fi
}

# Check if .env has been modified
check_env_changed() {
  local current_mtime
  current_mtime=$(get_env_mtime)
  
  if [[ -z "$LAST_ENV_MTIME" ]]; then
    LAST_ENV_MTIME="$current_mtime"
    return 1
  fi
  
  if [[ "$current_mtime" != "$LAST_ENV_MTIME" ]]; then
    return 0  # Changed
  fi
  
  return 1  # Not changed
}

# Initialize hot-reload functionality
init_hot_reload() {
  local repo_root="$1"
  REPO_ROOT_PATH="$(cd "$repo_root" && pwd)"
  ENV_FILE="${REPO_ROOT_PATH}/.env"
  
  # Capture initial config snapshot
  CONFIG_SNAPSHOT="$(capture_config_snapshot)"
  LAST_ENV_MTIME=$(get_env_mtime)
  
  # Set up signal handler for SIGHUP
  trap 'handle_sighup' HUP
  
  echo "[hot-reload] Initialized. Send SIGHUP or edit .env to reload config."
  echo "[hot-reload] Initial config: $(echo "$CONFIG_SNAPSHOT" | head -1)"
}

# Handle SIGHUP signal
handle_sighup() {
  RELOAD_REQUESTED=true
}

# Reload configuration from .env
reload_config() {
  echo "[hot-reload] Reloading configuration..."
  
  # Track old values for comparison
  local old_model="$OLLAMA_MODEL"
  local old_host="$OLLAMA_HOST"
  local old_interval="$INTERVAL"
  local old_forgejo="$FORGEJO_HOST"
  
  # Re-source .env with export
  if [[ -f "${REPO_ROOT_PATH}/.env" ]]; then
    set -a
    source "${REPO_ROOT_PATH}/.env" 2>/dev/null || true
    set +a
  else
    echo "[hot-reload] WARNING: .env not found at ${REPO_ROOT_PATH}/.env"
  fi
  
  # Set defaults if not in .env
  FORGEJO_HOST="${FORGEJO_HOST:-http://localhost:1234}"
  AUTH="${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}"
  OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
  OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5-coder:14b}"
  INTERVAL="${INTERVAL:-${POLL_INTERVAL:-60}}"
  
  # Log changes
  echo "[hot-reload] Configuration reloaded:"
  [[ "$old_model" != "$OLLAMA_MODEL" ]] && echo "  OLLAMA_MODEL: ${old_model:-<unset>} -> ${OLLAMA_MODEL}"
  [[ "$old_host" != "$OLLAMA_HOST" ]] && echo "  OLLAMA_HOST: ${old_host:-<unset>} -> ${OLLAMA_HOST}"
  [[ "$old_interval" != "$INTERVAL" ]] && echo "  INTERVAL: ${old_interval:-60} -> ${INTERVAL}"
  [[ "$old_forgejo" != "$FORGEJO_HOST" ]] && echo "  FORGEJO_HOST: ${old_forgejo:-<unset>} -> ${FORGEJO_HOST}"
  
  # Update snapshot and mtime
  CONFIG_SNAPSHOT="$(capture_config_snapshot)"
  LAST_ENV_MTIME=$(get_env_mtime)
  RELOAD_REQUESTED=false
  
  echo "[hot-reload] Reload complete."
}

# Interruptible sleep that checks for reload requests (SIGHUP or .env changes)
# Replaces: sleep "$INTERVAL"
interruptible_sleep() {
  local duration="${1:-60}"
  local elapsed=0
  local check_interval=3
  local last_check=0
  local last_mtime="0"
  
  # Get initial mtime
  last_mtime=$(get_env_mtime)
  
  while [[ $elapsed -lt $duration ]]; do
    # Only check every check_interval seconds
    if [[ $((elapsed - last_check)) -ge $check_interval ]]; then
      last_check=$elapsed
      
      local current_mtime
      current_mtime=$(get_env_mtime)
      
      # Check for file changes
      if [[ "$current_mtime" != "$last_mtime" ]]; then
        reload_config
        last_mtime="$current_mtime"
      fi
      
      if [[ "$RELOAD_REQUESTED" == true ]]; then
        reload_config
        RELOAD_REQUESTED=false
      fi
    fi
    
    sleep 1
    elapsed=$((elapsed + 1))
  done
}

# Capture current config as a single-line string for comparison
capture_config_snapshot() {
  echo "OLLAMA_MODEL=${OLLAMA_MODEL:-},OLLAMA_HOST=${OLLAMA_HOST:-},INTERVAL=${INTERVAL:-60},FORGEJO_HOST=${FORGEJO_HOST:-}"
}

# Reload configuration from .env
reload_config() {
  echo "[hot-reload] Reloading configuration..."
  
  # Track old values for comparison
  local old_model="$OLLAMA_MODEL"
  local old_host="$OLLAMA_HOST"
  local old_interval="$INTERVAL"
  local old_forgejo="$FORGEJO_HOST"
  
  # Re-source .env with export
  if [[ -f "${REPO_ROOT_PATH}/.env" ]]; then
    set -a
    source "${REPO_ROOT_PATH}/.env" 2>/dev/null || true
    set +a
  else
    echo "[hot-reload] WARNING: .env not found at ${REPO_ROOT_PATH}/.env"
  fi
  
  # Set defaults if not in .env
  FORGEJO_HOST="${FORGEJO_HOST:-http://localhost:1234}"
  AUTH="${FORGEJO_ADMIN_USER}:${FORGEJO_ADMIN_PASSWORD}"
  OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
  OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5-coder:14b}"
  INTERVAL="${INTERVAL:-${POLL_INTERVAL:-60}}"
  
  # Log changes
  echo "[hot-reload] Configuration reloaded:"
  [[ "$old_model" != "$OLLAMA_MODEL" ]] && echo "  OLLAMA_MODEL: ${old_model:-<unset>} -> ${OLLAMA_MODEL}"
  [[ "$old_host" != "$OLLAMA_HOST" ]] && echo "  OLLAMA_HOST: ${old_host:-<unset>} -> ${OLLAMA_HOST}"
  [[ "$old_interval" != "$INTERVAL" ]] && echo "  INTERVAL: ${old_interval:-60} -> ${INTERVAL}"
  [[ "$old_forgejo" != "$FORGEJO_HOST" ]] && echo "  FORGEJO_HOST: ${old_forgejo:-<unset>} -> ${FORGEJO_HOST}"
  
  # Update snapshot
  CONFIG_SNAPSHOT="$(capture_config_snapshot)"
  RELOAD_REQUESTED=false
  
  echo "[hot-reload] Reload complete."
}

# Interruptible sleep that checks for reload requests
# Replaces: sleep "$INTERVAL"
interruptible_sleep() {
  local duration="${1:-60}"
  local elapsed=0
  
  while [[ $elapsed -lt $duration ]]; do
    # Check if reload was requested
    if [[ "$RELOAD_REQUESTED" == true ]]; then
      reload_config
    fi
    
    sleep 1
    elapsed=$((elapsed + 1))
  done
}

# Check if reload is requested (non-blocking, for use in loops)
check_reload() {
  if [[ "$RELOAD_REQUESTED" == true ]]; then
    reload_config
    return 0
  fi
  return 1
}

# Get current reload status (for debugging)
is_reload_requested() {
  echo "$RELOAD_REQUESTED"
}
