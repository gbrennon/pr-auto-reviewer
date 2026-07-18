#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

CONFIG_DIR="${HOME}/.config/pr-auto-reviewer"
CONFIG_FILE="${CONFIG_DIR}/config"
SYSTEMD_DIR="${HOME}/.config/systemd/user"
SERVICE_NAME="pr-auto-reviewer.service"

# Backup existing config
if [ -f "$CONFIG_FILE" ]; then
    echo "Backing up existing config to $CONFIG_FILE.bak"
    cp "$CONFIG_FILE" "$CONFIG_FILE.bak"
fi

# Copy .env to config (production config file)
ENV_FILE="${REPO_ROOT}/.env"
if [ ! -f "$ENV_FILE" ]; then
    echo "Warning: .env not found at $ENV_FILE — skipping config update"
else
    mkdir -p "$CONFIG_DIR"
    cp "$ENV_FILE" "$CONFIG_FILE"
    echo "Config applied: $ENV_FILE → $CONFIG_FILE"
fi

# Install service file template
SERVICE_SRC="${SCRIPT_DIR}/pr-auto-reviewer.service"
SERVICE_DEST="${SYSTEMD_DIR}/${SERVICE_NAME}"
if [ ! -f "$SERVICE_SRC" ]; then
    echo "Error: service template not found at $SERVICE_SRC" >&2
    exit 1
fi
mkdir -p "$SYSTEMD_DIR"
cp "$SERVICE_SRC" "$SERVICE_DEST"
echo "Service file installed: $SERVICE_SRC → $SERVICE_DEST"

# Reload systemd and restart/start service
systemctl --user daemon-reload
if systemctl --user is-active --quiet "$SERVICE_NAME"; then
    systemctl --user restart "$SERVICE_NAME"
    echo "Service restarted: $SERVICE_NAME"
else
    systemctl --user start "$SERVICE_NAME"
    echo "Service started: $SERVICE_NAME"
fi

