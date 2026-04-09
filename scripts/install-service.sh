#!/usr/bin/env bash
# install-service.sh — Install PR AI Auto-Reviewer as a systemd user service

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

SYSTEMD_DIR="${HOME}/.config/systemd/user"
SERVICE_FILE="pr-ai-auto-reviewer.service"
SERVICE_NAME="pr-ai-auto-reviewer.service"

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
    if [[ -f "$SYSTEMD_DIR/$SERVICE_FILE" ]]; then
        echo "Service already installed, updating..."
        systemctl --user stop "$SERVICE_NAME" 2>/dev/null || true
        install_service
    else
        install_service
    fi
}

main "$@"