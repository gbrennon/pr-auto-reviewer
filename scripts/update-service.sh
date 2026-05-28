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

