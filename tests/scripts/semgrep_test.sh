#!/usr/bin/env bash
set -euo pipefail

root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"

command -v semgrep >/dev/null 2>&1 || {
    printf 'Semgrep is required to run fixture tests\n' >&2
    exit 127
}

fixture_root="$root/tests/fixtures/semgrep/src/pr_auto_reviewer"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

extract_rules() {
    local source="$1"
    local destination="$2"
    shift 2
    local ids="$*"
    {
        printf 'rules:\n'
        awk -v ids="$ids" '
            function selected(rule_id, wanted, count, position) {
                count = split(ids, wanted, " ")
                for (position = 1; position <= count; position++) {
                    if (wanted[position] == rule_id) {
                        return 1
                    }
                }
                return 0
            }
            /^  - id: / {
                if (active && keep) {
                    printf "%s", block
                }
                block = $0 ORS
                rule_id = $0
                sub(/^  - id: /, "", rule_id)
                keep = selected(rule_id)
                active = 1
                next
            }
            active {
                block = block $0 ORS
            }
            END {
                if (active && keep) {
                    printf "%s", block
                }
            }
        ' "$source"
    } > "$destination"
}

run_fixtures() {
    local config="$1"
    shift
    local fixtures=("$@")
    if ((${#fixtures[@]} == 0)); then
        printf 'No fixtures found for %s\n' "$config" >&2
        return 1
    fi
    local fixture flat
    for fixture in "${fixtures[@]}"; do
        flat="$(mktemp "$tmp_dir/fixture.XXXXXX.py")"
        cp "$fixture" "$flat"
        semgrep scan --test --config "$config" "$flat"
    done
}

mapfile -t architecture_fixtures < <(
    find "$fixture_root" -name architecture.py -type f | sort
)
mapfile -t convention_fixtures < <(
    find "$fixture_root" -name conventions.py -type f | sort
)
mapfile -t correctness_fixtures < <(
    find "$fixture_root" -name correctness.py -type f | sort
)

extract_rules \
    "$root/.semgrep/architecture.yml" \
    "$tmp_dir/domain.yml" \
    python-domain-no-outward-layer-dependencies
extract_rules \
    "$root/.semgrep/architecture.yml" \
    "$tmp_dir/application.yml" \
    python-application-no-presentation-dependencies \
    python-application-no-infrastructure-dependencies
extract_rules \
    "$root/.semgrep/architecture.yml" \
    "$tmp_dir/ports.yml" \
    python-application-ports-must-use-protocol

run_fixtures "$tmp_dir/domain.yml" \
    "$fixture_root/domain/entities/architecture.py"
run_fixtures "$tmp_dir/application.yml" \
    "$fixture_root/application/services/architecture.py"
run_fixtures "$tmp_dir/ports.yml" \
    "$fixture_root/application/ports/inbound/architecture.py" \
    "$fixture_root/application/ports/outbound/architecture.py"
run_fixtures "$root/.semgrep/conventions.yml" "${convention_fixtures[@]}"
run_fixtures "$root/.semgrep/correctness.yml" "${correctness_fixtures[@]}"
