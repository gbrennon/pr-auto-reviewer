#!/usr/bin/env bash
# test-unit.sh - Run unit tests with bashunit

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
BASHUNIT="${PROJECT_DIR}/lib/bashunit"
TESTS_DIR="${PROJECT_DIR}/tests"

if [[ ! -f "$BASHUNIT" ]]; then
    echo "bashunit not found. Installing..."
    bash "${SCRIPT_DIR}/install-bashunit.sh"
fi

echo "Running unit tests..."
"$BASHUNIT" "$TESTS_DIR"