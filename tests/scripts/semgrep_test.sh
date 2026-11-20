#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"

command -v semgrep >/dev/null 2>&1 || {
    printf 'Semgrep is required to run fixture tests\n' >&2
    exit 127
}

semgrep scan --test --config "$root/.semgrep" \
    "$root/tests/fixtures/semgrep"
