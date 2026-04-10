#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SYSTEMD_DIR="${HOME}/.config/systemd/user"
SERVICE_FILE="pr-ai-auto-reviewer.service"
SERVICE_NAME="pr-ai-auto-reviewer.service"
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

    cat > "$SYSTEMD_DIR/$SERVICE_FILE" <<EOF
[Unit]
Description=PR AI Auto-Reviewer
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${REPO_ROOT}
ExecStart=/usr/bin/bash ${REPO_ROOT}/scripts/watch-prs.sh
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
    echo "Check status: systemctl --user status $SERVICE_NAME"
}

main() {
    setup_config
    
    if [[ -f "$SYSTEMD_DIR/$SERVICE_FILE" ]]; then
        echo "Service already installed, updating..."
        systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
        install_service
    else
        install_service
    fi
}

main "$@"