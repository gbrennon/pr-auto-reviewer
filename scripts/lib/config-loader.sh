#!/usr/bin/env bash
# config-loader.sh — Load configuration from user config directory or repo

CONFIG_DIR="${HOME}/.config/pr-auto-reviewer"
CONFIG_FILE="${CONFIG_DIR}/config"
REPO_CONFIG="${REPO_ROOT:-.}/.env"

load_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        set -a
        source "$CONFIG_FILE"
        set +a
        return 0
    fi

    if [[ -f "$REPO_CONFIG" ]]; then
        set -a
        source "$REPO_CONFIG"
        set +a
        return 0
    fi

    echo "ERROR: No config file found at $CONFIG_FILE or $REPO_CONFIG" >&2
    return 1
}

get_config_path() {
    if [[ -f "$CONFIG_FILE" ]]; then
        echo "$CONFIG_FILE"
    elif [[ -f "$REPO_CONFIG" ]]; then
        echo "$REPO_CONFIG"
    else
        echo ""
    fi
}