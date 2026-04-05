#!/usr/bin/env bash
# 20-watch-prs.sh — Start AI PR reviewer watcher.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/lib.sh"

WATCH_PR_SCRIPT="${SCRIPT_DIR}/../watch-prs.sh"
PID_FILE="${REPO_ROOT}/runner-data/watch-prs.pid"
LOG_FILE="${REPO_ROOT}/watch-prs.log"

start() {
  if [[ ! -f "$WATCH_PR_SCRIPT" ]]; then
    log_warn "watch-prs.sh not found"
    return 0
  fi
  
  if ! curl -sf "${OLLAMA_HOST:-http://localhost:11434}/api/tags" >/dev/null 2>&1; then
    log_warn "Ollama not available, skipping PR watcher"
    return 0
  fi
  
  log "Starting PR watcher..."
  run_background "$WATCH_PR_SCRIPT" "$PID_FILE" "watch-prs" "$LOG_FILE"
}

stop() {
  stop_background "$PID_FILE" "watch-prs"
}

start
