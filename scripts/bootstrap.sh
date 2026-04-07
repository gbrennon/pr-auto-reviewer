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
  if [[ -f "$REPO_ROOT/.env" ]]; then
    log_info ".env loaded"
  else
    log_error ".env not found. Create it from .env.example template."
    return 1
  fi

  init_env
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

  if [[ ! -f "$REPO_ROOT/.env" ]]; then
    log_error ".env file missing. Run bootstrap again after configuring."
    return 1
  fi

  if [[ -z "$CODEBERG_TOKEN" ]]; then
    log_warn "CODEBERG_TOKEN is empty. Reviews will fail for private repos."
  fi

  if bash "$REPO_ROOT/scripts/autostart/autostart.sh" --status 2>/dev/null | grep -q "watch-prs.*running"; then
    log_info "watch-prs is already running, skipping start"
    return 0
  fi

  log_info "watch-prs not running, starting..."
  bash "$REPO_ROOT/scripts/autostart/autostart.sh"
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
