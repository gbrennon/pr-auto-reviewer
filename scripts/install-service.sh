#!/usr/bin/env bash
# install-service.sh — Install pr-auto-reviewer: shell aliases for systemd +
# CLI available in PATH
#
# 1. Creates shell aliases so you can control the systemd service with short commands:
#      pr-reviewer start / stop / status / logs / restart
#
# 2. Installs the pr-auto-reviewer CLI globally via `uv tool install --editable`
#    so you can run it directly without going through systemd:
#      pr-auto-reviewer --help

set -euo pipefail

SERVICE_NAME="pr-auto-reviewer.service"
FUNC_NAME="pr-reviewer"

# ── OS detection ────────────────────────────────────────────────────────────
detect_os() {
    case "$(uname -s)" in
        Linux)  echo "linux" ;;
        Darwin) echo "macos" ;;
        *)      echo "unknown" ;;
    esac
}

OS=$(detect_os)

if [[ "$OS" != "linux" ]]; then
    echo "systemd is not available on $OS. No aliases created."
    exit 0
fi

# ── Shell detection ─────────────────────────────────────────────────────────
detect_shell() {
    local shell_name
    shell_name=$(basename "${SHELL:-/bin/bash}")

    # The SHELL env var always points to the login shell.
    # We trust it for bash/zsh.  For fish we also check its own variable.
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

# ── Config file path ────────────────────────────────────────────────────────
case "$SHELL_NAME" in
    fish) RC_FILE="${HOME}/.config/fish/config.fish" ;;
    zsh)  RC_FILE="${HOME}/.zshrc" ;;
    bash) RC_FILE="${HOME}/.bashrc" ;;
esac

# ── Generate the shell function ─────────────────────────────────────────────
case "$SHELL_NAME" in
    fish)
        # fish uses a different syntax for functions and strings
        FUNCTION_BLOCK="# pr-auto-reviewer aliases — installed by install-service.sh
function ${FUNC_NAME}
    switch \$argv[1]
        case start
            systemctl --user start ${SERVICE_NAME}
        case stop
            systemctl --user stop ${SERVICE_NAME}
        case status
            systemctl --user status ${SERVICE_NAME}
        case logs
            journalctl --user -u ${SERVICE_NAME} -f
        case restart
            systemctl --user restart ${SERVICE_NAME}
        case '*'
            echo 'Usage: ${FUNC_NAME} {start|stop|status|logs|restart}'
            return 1
    end
end"
        GREP_PATTERN="function ${FUNC_NAME}"
        ACTIVATE_CMD="source ${RC_FILE}"
        ;;
    *)
        # bash / zsh (POSIX)
        FUNCTION_BLOCK="# pr-auto-reviewer aliases — installed by install-service.sh
${FUNC_NAME}() {
    case \"\$1\" in
        start)   systemctl --user start ${SERVICE_NAME} ;;
        stop)    systemctl --user stop ${SERVICE_NAME} ;;
        status)  systemctl --user status ${SERVICE_NAME} ;;
        logs)    journalctl --user -u ${SERVICE_NAME} -f ;;
        restart) systemctl --user restart ${SERVICE_NAME} ;;
        *)
            echo \"Usage: ${FUNC_NAME} {start|stop|status|logs|restart}\"
            return 1
            ;;
    esac
}"
        GREP_PATTERN="${FUNC_NAME}()"
        ACTIVATE_CMD="source ${RC_FILE}"
        ;;
esac

# ── Interactive shell detection message ─────────────────────────────────────
echo "Detected shell: ${SHELL_NAME}"
echo "Config file:    ${RC_FILE}"
echo ""

# ── Persist (idempotent — skip if already present) ──────────────────────────
if grep -qF "${GREP_PATTERN}" "${RC_FILE}" 2>/dev/null; then
    echo "Aliases already present — nothing to do."
else
    # Ensure parent directory exists (fish config dir may not)
    mkdir -p "$(dirname "${RC_FILE}")"
    echo "" >> "${RC_FILE}"
    echo "${FUNCTION_BLOCK}" >> "${RC_FILE}"
    echo "Aliases written."
    echo ""
    echo "Run this to activate now:"
    echo "  ${ACTIVATE_CMD}"
    echo ""
    echo "Then use:"
    echo "  ${FUNC_NAME} start"
    echo "  ${FUNC_NAME} stop"
    echo "  ${FUNC_NAME} status"
    echo "  ${FUNC_NAME} logs"
    echo "  ${FUNC_NAME} restart"
fi

# ── Install CLI in PATH ─────────────────────────────────────────────────────
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo ""
echo "Installing pr-auto-reviewer CLI..."

if command -v uv &>/dev/null; then
    if uv tool install --editable "$PROJECT_ROOT" 2>&1; then
        echo "CLI installed: 'pr-auto-reviewer' is now available in PATH"
        echo "Try: pr-auto-reviewer --help"
    fi
else
    echo "Warning: uv not found — CLI not installed in PATH"
    echo "Install uv (https://docs.astral.sh/uv/) or run: pip install --editable ."
fi
