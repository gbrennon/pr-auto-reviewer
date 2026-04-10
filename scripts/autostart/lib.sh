#!/usr/bin/env bash
# lib.sh — Shared utilities for autostart scripts.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

CONFIG_FILE="${HOME}/.config/pr-auto-reviewer/config"
REPO_ENV="${REPO_ROOT}/.env"

if [[ -f "$CONFIG_FILE" ]]; then
  set -a
  source "$CONFIG_FILE"
  set +a
elif [[ -f "$REPO_ENV" ]]; then
  set -a
  source "$REPO_ENV"
  set +a
fi

log() {
  printf '[autostart] %s\n' "$1"
}

log_skip() {
  printf '[autostart] [SKIP] %s\n' "$1"
}

log_start() {
  printf '[autostart] [START] %s\n' "$1"
}

log_done() {
  printf '[autostart] [DONE] %s\n' "$1"
}

log_warn() {
  printf '[autostart] [WARN] %s\n' "$1"
}

log_error() {
  printf '[autostart] [ERROR] %s\n' "$1"
}

is_running() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    local pid
    pid=$(cat "$pid_file" 2>/dev/null)
    if [[ -n "$pid" ]] && kill -0 "$pid" 2>/dev/null; then
      return 0
    fi
  fi
  return 1
}

get_pid() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    cat "$pid_file"
  fi
}

run_background() {
  local script="$1"
  local pid_file="$2"
  local name="$3"
  local logs="${4:-/dev/null}"
  
  if is_running "$pid_file"; then
    log_skip "$name already running (PID $(get_pid "$pid_file"))"
    return 0
  fi
  
  rm -f "$pid_file"
  
  if [[ "$logs" != "/dev/null" ]]; then
    mkdir -p "$(dirname "$logs")"
  fi

  log_start "$name"
  
  {
    set -a
    if [[ -f "$CONFIG_FILE" ]]; then
      source "$CONFIG_FILE"
    elif [[ -f "$REPO_ENV" ]]; then
      source "$REPO_ENV"
    fi
    set +a
    exec bash "$script"
  } >> "$logs" 2>&1 &
  
  local new_pid=$!
  echo "$new_pid" > "$pid_file"
  
  log_done "$name started (PID $new_pid)"
  return 0
}

stop_background() {
  local pid_file="$1"
  local name="$2"
  
  if is_running "$pid_file"; then
    local pid
    pid=$(get_pid "$pid_file")
    log "Stopping $name (PID $pid)..."
    kill "$pid" 2>/dev/null || true
    sleep 1
    rm -f "$pid_file"
    log_done "$name stopped"
  else
    log_skip "$name not running"
  fi
}
