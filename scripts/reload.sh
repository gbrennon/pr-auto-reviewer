#!/usr/bin/env bash
# reload.sh — Send SIGHUP to running watchers to reload configuration.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

PID_FILES=(
  "runner-data/watch-prs.pid"
  "watcher-prs.pid"
)

log_info() {
  echo "[reload] $*"
}

log_error() {
  echo "[reload] ERROR: $*" >&2
}

log_skip() {
  echo "[reload] SKIP: $*"
}

check_pid() {
  local pidfile="$1"
  local full_path="$REPO_ROOT/$pidfile"
  
  if [[ ! -f "$full_path" ]]; then
    return 1
  fi
  
  local pid
  pid=$(cat "$full_path" 2>/dev/null)
  
  if [[ -z "$pid" ]]; then
    return 1
  fi
  
  if kill -0 "$pid" 2>/dev/null; then
    return 0
  fi
  
  return 1
}

send_sighup() {
  local pidfile="$1"
  local full_path="$REPO_ROOT/$pidfile"
  local pid
  
  pid=$(cat "$full_path" 2>/dev/null)
  
  if kill -HUP "$pid" 2>/dev/null; then
    log_info "Sent SIGHUP to $(basename "$pidfile" .pid) (PID: $pid)"
    return 0
  else
    log_error "Failed to send SIGHUP to PID $pid"
    return 1
  fi
}

show_status() {
  log_info "Hot-reloadable processes:"
  echo ""
  
  local found_any=false
  
  for pidfile in "${PID_FILES[@]}"; do
    local full_path="$REPO_ROOT/$pidfile"
    local name
    name=$(basename "$pidfile" .pid)
    
    if [[ -f "$full_path" ]]; then
      local pid
      pid=$(cat "$full_path" 2>/dev/null || echo "unknown")
      
      if kill -0 "$pid" 2>/dev/null; then
        echo "  ✓ $name: running (PID $pid)"
        found_any=true
      else
        echo "  ✗ $name: not running (stale PID file)"
      fi
    else
      echo "  - $name: not running"
    fi
  done
  
  echo ""
  if [[ "$found_any" == false ]]; then
    log_info "No reloadable processes running."
  fi
}

main() {
  local action="reload"
  
  for arg in "$@"; do
    case "$arg" in
      -h|--help)
        echo "Usage: $(basename "$0") [options]"
        echo "Options: --status, -h, --help"
        exit 0
        ;;
      --status)
        action="status"
        ;;
    esac
  done
  
  case "$action" in
    status)
      show_status
      ;;
    reload)
      log_info "Reloading watchers..."
      echo ""
      
      local reloaded=0
      local skipped=0
      
      for pidfile in "${PID_FILES[@]}"; do
        if check_pid "$pidfile"; then
          send_sighup "$pidfile" && ((reloaded++)) || ((skipped++))
        else
          log_skip "$(basename "$pidfile" .pid): not running"
          ((skipped++))
        fi
      done
      
      echo ""
      log_info "Reload complete: $reloaded signaled, $skipped skipped"
      ;;
  esac
}

main "$@"
