#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

CONFIG_DIR="${HOME}/.config/pr-auto-reviewer"
CONFIG_FILE="${CONFIG_DIR}/config"

SYSTEMD_DIR="${HOME}/.config/systemd/user"
SERVICE_NAME="pr-auto-reviewer.service"
CONFIG_DIR="${HOME}/.config/pr-auto-reviewer"
CONFIG_FILE="${CONFIG_DIR}/config"

setup_config() {
    if [[ -f "$CONFIG_FILE" ]]; then
        echo "Config already exists at $CONFIG_FILE — updating format..."
        local tmp_file="${CONFIG_FILE}.new"
        cp "$CONFIG_FILE" "$CONFIG_FILE.bak.$(date +%Y%m%d-%H%M%S)"

        # Read existing values
        local existing_token=$(grep -oP '^FORGEJO_TOKEN=\K.*' "$CONFIG_FILE" 2>/dev/null || true)
        local existing_reviewer=$(grep -oP '^FORGEJO_REVIEWER_TOKEN=\K.*' "$CONFIG_FILE" 2>/dev/null || true)
        local existing_username=$(grep -oP '^FORGEJO_REVIEWER_USERNAME=\K.*' "$CONFIG_FILE" 2>/dev/null || true)
        local existing_host=$(grep -oP '^FORGEJO_HOST=\K.*' "$CONFIG_FILE" 2>/dev/null || true)
        local existing_platform_mode=$(grep -oP '^PLATFORM_MODE=\K.*' "$CONFIG_FILE" 2>/dev/null || true)
        local existing_gh_token=$(grep -oP '^GITHUB_TOKEN=\K.*' "$CONFIG_FILE" 2>/dev/null || true)
        local existing_gh_reviewer=$(grep -oP '^GITHUB_REVIEWER_TOKEN=\K.*' "$CONFIG_FILE" 2>/dev/null || true)
        local existing_gh_username=$(grep -oP '^GITHUB_REVIEWER_USERNAME=\K.*' "$CONFIG_FILE" 2>/dev/null || true)
        local existing_ollama_host=$(grep -oP '^OLLAMA_HOST=\K.*' "$CONFIG_FILE" 2>/dev/null || true)
        local existing_ollama_model=$(grep -oP '^OLLAMA_MODEL=\K.*' "$CONFIG_FILE" 2>/dev/null || true)
        local existing_poll=$(grep -oP '^POLL_INTERVAL=\K.*' "$CONFIG_FILE" 2>/dev/null || true)

        cat > "$CONFIG_FILE" <<'EOF'
# PR Auto-Reviewer Configuration
#
# Platform: github, codeberg, or both.  Leave tokens blank for platforms you
# don't use — missing/bad tokens are logged and skipped, not fatal.

# === PLATFORM ===
PLATFORM_MODE=both

# === GITHUB ===
GITHUB_TOKEN=
GITHUB_REVIEWER_TOKEN=
GITHUB_REVIEWER_USERNAME=

# === CODEBERG / FORGEJO ===
FORGEJO_TOKEN=EXISTING_TOKEN_PLACEHOLDER
FORGEJO_REVIEWER_TOKEN=EXISTING_REVIEWER_PLACEHOLDER
FORGEJO_REVIEWER_USERNAME=EXISTING_USERNAME_PLACEHOLDER
FORGEJO_HOST=EXISTING_HOST_PLACEHOLDER

# === API (usually auto-detected, override if needed) ===
# PLATFORM_API_URL=https://codeberg.org/api/v1

# === OLLAMA ===
OLLAMA_HOST=EXISTING_OLLAMA_HOST_PLACEHOLDER
OLLAMA_MODEL=EXISTING_OLLAMA_MODEL_PLACEHOLDER
POLL_INTERVAL=EXISTING_POLL_PLACEHOLDER

# === REVIEW MODE ===
GITHUB_REVIEW_MODE=formal

# === DEBUG ===
DEBUG=0
EOF
        # Restore existing values
        sed -i "s|^PLATFORM_MODE=.*|PLATFORM_MODE=${existing_platform_mode:-codeberg}|" "$CONFIG_FILE"
        sed -i "s|^GITHUB_TOKEN=.*|GITHUB_TOKEN=${existing_gh_token}|" "$CONFIG_FILE"
        sed -i "s|^GITHUB_REVIEWER_TOKEN=.*|GITHUB_REVIEWER_TOKEN=${existing_gh_reviewer}|" "$CONFIG_FILE"
        sed -i "s|^GITHUB_REVIEWER_USERNAME=.*|GITHUB_REVIEWER_USERNAME=${existing_gh_username}|" "$CONFIG_FILE"
        sed -i "s|^FORGEJO_TOKEN=.*|FORGEJO_TOKEN=${existing_token}|" "$CONFIG_FILE"
        sed -i "s|^FORGEJO_REVIEWER_TOKEN=.*|FORGEJO_REVIEWER_TOKEN=${existing_reviewer}|" "$CONFIG_FILE"
        sed -i "s|^FORGEJO_REVIEWER_USERNAME=.*|FORGEJO_REVIEWER_USERNAME=${existing_username}|" "$CONFIG_FILE"
        sed -i "s|^FORGEJO_HOST=.*|FORGEJO_HOST=${existing_host}|" "$CONFIG_FILE"
        sed -i "s|^OLLAMA_HOST=.*|OLLAMA_HOST=${existing_ollama_host}|" "$CONFIG_FILE"
        sed -i "s|^OLLAMA_MODEL=.*|OLLAMA_MODEL=${existing_ollama_model}|" "$CONFIG_FILE"
        sed -i "s|^POLL_INTERVAL=.*|POLL_INTERVAL=${existing_poll}|" "$CONFIG_FILE"
        echo "Config updated. Previous version backed up to $CONFIG_FILE.bak.*"
    else
        mkdir -p "$CONFIG_DIR"
        cat > "$CONFIG_FILE" <<'EOF'
# PR Auto-Reviewer Configuration
#
# Platform: github, codeberg, or both.  Leave tokens blank for platforms you
# don't use — missing/bad tokens are logged and skipped, not fatal.

# === PLATFORM ===
PLATFORM_MODE=both

# === GITHUB ===
GITHUB_TOKEN=
GITHUB_REVIEWER_TOKEN=
GITHUB_REVIEWER_USERNAME=

# === CODEBERG / FORGEJO ===
FORGEJO_TOKEN=
FORGEJO_REVIEWER_TOKEN=
FORGEJO_REVIEWER_USERNAME=
FORGEJO_HOST=https://codeberg.org

# === OLLAMA ===
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=             # Required
POLL_INTERVAL=60

# === REVIEW MODE ===
GITHUB_REVIEW_MODE=formal

# === DEBUG ===
DEBUG=0
EOF
        echo "Config created. Please edit $CONFIG_FILE with your tokens and model."
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
Environment=ENV=production
Environment=PYTHONUNBUFFERED=1
EnvironmentFile=${CONFIG_FILE}
ExecStart=${REPO_ROOT}/.venv/bin/python -m pr_auto_reviewer watch-prs
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
EOF

    echo "Installing Python dependencies..."
    (cd "$REPO_ROOT" && uv sync)

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
