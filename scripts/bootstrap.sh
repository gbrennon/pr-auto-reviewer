#!/usr/bin/env bash
# bootstrap.sh — Bootstrap script to start the PR AI Auto-Reviewer

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

source "${SCRIPT_DIR}/lib/env-loader.sh"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[bootstrap]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[bootstrap]${NC} WARNING: $*"; }
log_error() { echo -e "${RED}[bootstrap]${NC} ERROR: $*"; }

check_dep() {
  if ! command -v "$1" &>/dev/null; then
    log_error "$1 is required but not installed"
    return 1
  fi
  log_info "$1 found: $(command -v "$1")"
}

check_deps() {
  log_info "Checking dependencies..."
  check_dep curl || true
  check_dep python3 || true
  check_dep flock || true
  check_dep nohup || true
}

setup_env() {
  if [[ -f "${HOME}/.config/pr-auto-reviewer/config" ]]; then
    log_info "Using user config: ~/.config/pr-auto-reviewer/config"
    set -a
    source "${HOME}/.config/pr-auto-reviewer/config"
    set +a
    return 0
  fi

  if [[ -f "$REPO_ROOT/.env" ]]; then
    log_info ".env loaded from repo"
    set -a
    source "$REPO_ROOT/.env"
    set +a
    return 0
  fi

  log_error "No config found. Either:"
  log_error "  - Install: bash scripts/install-service.sh"
  log_error "  - Manual: cp .env.example .env and edit"
  return 1
}

check_service_status() {
  if systemctl --user is-active --quiet pr-auto-reviewer.service 2>/dev/null; then
    return 0
  fi
  return 1
}

pause_service() {
  if check_service_status; then
    log_info "Pausing systemd service..."
    
    systemctl --user stop pr-auto-reviewer.service 2>/dev/null || true
    systemctl --user disable --now pr-auto-reviewer.service 2>/dev/null || true
    
    sleep 2
    
    local pids
    pids=$(pgrep -f "/scripts/watch-prs.sh" 2>/dev/null || true)
    if [[ -n "$pids" ]]; then
      log_info "Killing old watch-prs: $pids"
      for pid in $pids; do
        kill -9 "$pid" 2>/dev/null || true
      done
    fi
    
    rm -f "$REPO_ROOT/watcher-prs.lock" 2>/dev/null || true
    rm -f "$REPO_ROOT/watcher-prs.pid" 2>/dev/null || true
    
    sleep 1
    return 0
  fi
  return 1
}

resume_service() {
  log_info "Resuming systemd service..."
  systemctl --user enable --now pr-auto-reviewer.service 2>/dev/null || true
}

check_ollama() {
  local host="${OLLAMA_HOST:-http://localhost:11434}"

  log_info "Checking Ollama at $host..."
  if curl -sf "$host/api/tags" &>/dev/null; then
    log_info "Ollama is running"
    return 0
  else
    log_warn "Ollama not running at $host"
    return 1
  fi
}

start_ollama() {
  if command -v ollama &>/dev/null; then
    log_info "Starting Ollama..."
    nohup ollama serve &>/dev/null &
    sleep 3
    if check_ollama; then
      log_info "Ollama started"
    fi
  else
    log_warn "ollama command not found, cannot auto-start"
  fi
}

create_dirs() {
  mkdir -p "$REPO_ROOT/runner-data"
  mkdir -p "$REPO_ROOT/logs"
}

start_project() {
  log_info "Starting PR AI Auto-Reviewer..."

  local service_was_running=false

  if check_service_status; then
    log_info "Systemd service is running, pausing for manual validation..."
    pause_service
    service_was_running=true
  fi

  if [[ -z "$FORGEJO_TOKEN" ]]; then
    log_warn "FORGEJO_TOKEN is empty. Reviews will fail for private repos."
  fi

  log_info "Running pr-auto-reviewer daemon-once (single cycle)..."
  log_info "To stop early: Ctrl+C"
  log_info "Service will resume after this completes or is interrupted."

  if timeout 300 python -m pr_auto_reviewer watch-prs --once; then
    log_info "daemon-once completed"
  else
    log_warn "daemon-once interrupted or timed out"
  fi

  if [[ "$service_was_running" == "true" ]]; then
    log_info "Resuming systemd service..."
    resume_service
  fi
}

main() {
  echo ""
  echo "=== PR AI Auto-Reviewer Bootstrap ==="
  echo ""

  create_dirs
  check_deps
  setup_env

  if ! check_ollama; then
    start_ollama
  fi

  start_project

  echo ""
  log_info "Bootstrap complete"
  log_info "Use: bash scripts/autostart/autostart.sh --status to check status"
}

main "$@"
