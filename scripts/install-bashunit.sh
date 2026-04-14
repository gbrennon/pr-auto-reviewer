#!/usr/bin/env bash
# install-bashunit.sh - Install bashunit testing framework

set -e

BASHUNIT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../lib" && pwd)"
BASHUNIT_BIN="${BASHUNIT_DIR}/bashunit"

if [[ -f "$BASHUNIT_BIN" ]]; then
    echo "bashunit already installed at $BASHUNIT_BIN"
    exit 0
fi

echo "Installing bashunit..."
curl -s https://bashunit.typeddevs.com/install.sh | bash

echo "Done."