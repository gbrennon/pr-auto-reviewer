#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

if ! command -v systemctl &>/dev/null; then
    echo "ERROR: systemd is required. This script uses systemd user services." >&2
    exit 1
fi

if ! command -v python &>/dev/null; then
    echo "ERROR: python is required to run pr-auto-reviewer." >&2
    exit 1
fi

SYSTEMD_DIR="${HOME}/.config/systemd/user"
SERVICE_NAME="pr-auto-reviewer.service"
CONFIG_DIR="${HOME}/.config/pr-auto-reviewer"
CONFIG_FILE="${CONFIG_DIR}/config"

setup_config() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        echo "Creating config at $CONFIG_FILE..."
        mkdir -p "$CONFIG_DIR"
        cat > "$CONFIG_FILE" <<'EOF'
# PR Auto-Reviewer Configuration

# === FORGEJO/CODEBERG ===
FORGEJO_TOKEN=           # Required - Generate at https://codeberg.org/settings/applications (scopes: repo, read:user)
FORGEJO_MODE=codeberg    # "local" or "codeberg" (default: codeberg)
FORGEJO_HOST=https://codeberg.org

# === REVIEWER ===
FORGEJO_REVIEWER_TOKEN=  # Required - Different user's token (scopes: repo)
FORGEJO_REVIEWER_USERNAME=  # Required

# === OLLAMA ===
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=             # Required - Your model (e.g., code-review, llama3.2, qwen2.5-coder:14b)
POLL_INTERVAL=60

# === DEBUG ===
DEBUG=0
EOF
        echo "Config created. Please edit $CONFIG_FILE with your tokens and model."
    else
        echo "Config already exists at $CONFIG_FILE"
    fi
}

install_service() {
    echo "Installing $SERVICE_NAME to $SYSTEMD_DIR/"
    mkdir -p "$SYSTEMD_DIR"

    cat > "$SYSTEMD_DIR/$SERVICE_NAME" <<EOF
[Unit]
Description=PR Auto Reviewer — AI-powered code review daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${REPO_ROOT}
EnvironmentFile=${CONFIG_FILE}
ExecStart=${REPO_ROOT}/.venv/bin/python -m pr_auto_reviewer watch-prs
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
EOF

    echo "Reloading systemd user daemon..."
    systemctl --user daemon-reload

    echo "Enabling service to start on login..."
    systemctl --user enable "$SERVICE_NAME"

    echo "Starting service..."
    systemctl --user restart "$SERVICE_NAME"

    echo ""
    echo "Service installed and started"
    echo "Check status:  systemctl --user status $SERVICE_NAME"
    echo "View logs:     journalctl --user -u $SERVICE_NAME -f"
    echo "Stop:          systemctl --user stop $SERVICE_NAME"
}

# ── main ───────────────────────────────────────────────────────────

main() {
    setup_config

    # Stop old service if it exists (migration from pr-ai-auto-reviewer)
    local old_service="pr-ai-auto-reviewer.service"
    if [[ -f "$SYSTEMD_DIR/$old_service" ]]; then
        echo "Removing old service $old_service..."
        systemctl --user stop "$old_service" 2>/dev/null || true
        systemctl --user disable "$old_service" 2>/dev/null || true
        rm -f "$SYSTEMD_DIR/$old_service"
        systemctl --user daemon-reload
    fi

    if [[ -f "$SYSTEMD_DIR/$SERVICE_NAME" ]]; then
        echo "Service already installed, updating..."
        systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
    fi
    install_service
}

main "$@"
