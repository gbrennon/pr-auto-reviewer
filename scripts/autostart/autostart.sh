#!/usr/bin/env bash
# autostart.sh — Main entry for autostart scripts.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

ACTION="${1:-run}"

log() {
  printf '[autostart] %s\n' "$1"
}

log_done() {
  printf '[autostart] [DONE] %s\n' "$1"
}

log_error() {
  printf '[autostart] [ERROR] %s\n' "$1"
}

run_all() {
  log "Running autostart scripts..."
  
  for script in "$SCRIPT_DIR"/[0-9][0-9]-*.sh; do
    [[ -f "$script" ]] || continue
    [[ "$(basename "$script")" == "lib.sh" ]] && continue
    [[ "$(basename "$script")" == "autostart.sh" ]] && continue
    
    log "Running $(basename "$script")"
    
    if source "$script" 2>/dev/null; then
      if declare -f start >/dev/null 2>&1; then
        start
      fi
      log_done "$(basename "$script")"
    else
      log_error "$(basename "$script") failed to source"
    fi
  done
  
  log "Autostart complete"
}

status_all() {
  log "Autostart script status:"
  
  for script in "$SCRIPT_DIR"/[0-9][0-9]-*.sh; do
    [[ -f "$script" ]] || continue
    [[ "$(basename "$script")" == "lib.sh" ]] && continue
    [[ "$(basename "$script")" == "autostart.sh" ]] && continue
    
    local name
    name=$(basename "$script" | sed 's/[0-9][0-9]-//; s/.sh$//')
    
    local pid_info="stopped"
    case "$name" in
      watch-prs)
        if pgrep -f "watch-prs.sh" >/dev/null 2>&1; then
          pid_info="running"
        fi
        ;;
    esac
    
    printf '  %-30s %s\n' "$name" "$pid_info"
  done
}

stop_all() {
  log "Stopping autostart scripts..."
  
  for script in "$SCRIPT_DIR"/[0-9][0-9]-*.sh; do
    [[ -f "$script" ]] || continue
    [[ "$(basename "$script")" == "lib.sh" ]] && continue
    [[ "$(basename "$script")" == "autostart.sh" ]] && continue
    
    if source "$script" 2>/dev/null; then
      if declare -f stop >/dev/null 2>&1; then
        log "Stopping $(basename "$script")"
        stop
      fi
    fi
  done
  
  log "Autostart stopped"
}

case "$ACTION" in
  --status)
    status_all
    ;;
  --stop)
    stop_all
    ;;
  *)
    run_all
    ;;
esac
