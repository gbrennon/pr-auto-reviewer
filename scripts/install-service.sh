#!/usr/bin/env bash
# install-service.sh — Install pr-auto-reviewer CLI globally
#
# Installs the pr-auto-reviewer CLI via `uv tool install` (real install — no
# symlink, fully isolated) and cleans up any old shell aliases (the `pr-reviewer`
# function) since the CLI now has built-in service commands:
#
#   pr-auto-reviewer start / stop / status / logs / restart

set -euo pipefail

# ── Helper ──────────────────────────────────────────────────────────────────
confirm() {
    local prompt="$1"
    local default="${2:-n}"
    local answer
    read -r -p "$prompt " answer
    answer="${answer:-$default}"
    case "$answer" in
        [Yy]*) return 0 ;;
        *)     return 1 ;;
    esac
}

OLD_FUNC_NAME="pr-reviewer"
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOL_NAME="pr-auto-reviewer"

# ── Shell detection (for rc file cleanup) ──────────────────────────────────
detect_shell() {
    local shell_name
    shell_name=$(basename "${SHELL:-/bin/bash}")

    if [[ -n "${FISH_VERSION:-}" ]]; then
        echo "fish"
        return
    fi

    case "$shell_name" in
        fish) echo "fish" ;;
        zsh)  echo "zsh" ;;
        bash) echo "bash" ;;
        *)    echo "bash" ;;
    esac
}

SHELL_NAME=$(detect_shell)

case "$SHELL_NAME" in
    fish) RC_FILE="${HOME}/.config/fish/config.fish"
          GREP_PATTERN="function ${OLD_FUNC_NAME}" ;;
    zsh)  RC_FILE="${HOME}/.zshrc"
          GREP_PATTERN="${OLD_FUNC_NAME}()" ;;
    bash) RC_FILE="${HOME}/.bashrc"
          GREP_PATTERN="${OLD_FUNC_NAME}()" ;;
esac

# ── Clean up old shell aliases ──────────────────────────────────────────────
if grep -qF "${GREP_PATTERN}" "${RC_FILE}" 2>/dev/null; then
    echo "Found old '${OLD_FUNC_NAME}' shell function in ${RC_FILE}"
    echo "(The CLI now has built-in service commands: ${TOOL_NAME} start/stop/status/logs/restart)"
    echo ""

    if confirm "Remove old '${OLD_FUNC_NAME}' function? [Y/n]" "y"; then
        sed -i '/^# pr-auto-reviewer aliases/,/^}\|^end$/d' "${RC_FILE}" 2>/dev/null || true
        echo "Old aliases removed from ${RC_FILE}"
    else
        echo "Old aliases left in place."
    fi
    echo ""
fi

# ── Apply .env to global config ──────────────────────────────────────────
CONFIG_DIR="${HOME}/.config/pr-auto-reviewer"
CONFIG_FILE="${CONFIG_DIR}/config"
ENV_FILE="${PROJECT_ROOT}/.env"
ENV_EXAMPLE="${PROJECT_ROOT}/.env.example"

if [ ! -f "$ENV_FILE" ]; then
    echo "Warning: .env not found at $ENV_FILE"
    if [ -f "$ENV_EXAMPLE" ]; then
        echo "Run: cp .env.example .env and edit it with your tokens, then re-run this script"
    fi
elif [ -f "$ENV_EXAMPLE" ] && cmp -s "$ENV_FILE" "$ENV_EXAMPLE"; then
    echo "Warning: .env appears to be the unmodified example template"
    echo "Edit $ENV_FILE with your tokens, then re-run this script"
else
    mkdir -p "$CONFIG_DIR"

    if [ -f "$CONFIG_FILE" ]; then
        if ! cmp -s "$ENV_FILE" "$CONFIG_FILE"; then
            echo "Backing up existing config to $CONFIG_FILE.bak"
            cp "$CONFIG_FILE" "$CONFIG_FILE.bak"
        fi
    fi

    cp "$ENV_FILE" "$CONFIG_FILE"
    echo "Config applied: $ENV_FILE → $CONFIG_FILE"
fi
echo ""

# ── Install CLI in PATH ─────────────────────────────────────────────────────
if ! command -v uv &>/dev/null; then
    echo "Warning: uv not found — CLI not installed in PATH"
    echo "Install uv (https://docs.astral.sh/uv/) or run: pip install ."
    exit 1
fi

if uv tool list 2>/dev/null | grep -q "^${TOOL_NAME} "; then
    if ! confirm "${TOOL_NAME} is already installed. Reinstall? [y/N]"; then
        echo "Skipped — CLI unchanged."
        exit 0
    fi
fi

echo "Installing ${TOOL_NAME} CLI..."
if uv tool install --force --reinstall "$PROJECT_ROOT" 2>&1; then
    echo ""
    echo "CLI installed: '${TOOL_NAME}' is now available in PATH"
    echo ""
    echo "Service commands:"
    echo "  ${TOOL_NAME} start     Start the daemon"
    echo "  ${TOOL_NAME} stop      Stop the daemon"
    echo "  ${TOOL_NAME} status    Show daemon status"
    echo "  ${TOOL_NAME} logs      Follow daemon logs"
    echo "  ${TOOL_NAME} restart   Restart the daemon"
    echo ""
    echo "Try: ${TOOL_NAME} --help"
fi
