#!/usr/bin/env bash
# Test library functions using bashunit

LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts/lib" && pwd)"

function test_extract_review_items_extracts_three_items() {
    local review_body='## AI Code Review

**Verdict:** Changes Requested

### Issues
1. [HIGH] [security] src/auth.rs:45: SQL injection vulnerability
2. [MEDIUM] [architecture] src/db.rs:20: Tight coupling

### Suggestions
3. Consider adding unit tests

**Summary:** Fix the security issue.'

    local result
    result=$(echo "$review_body" | python3 "${LIB_DIR}/extract_review_items.py")

    local count
    count=$(echo "$result" | wc -l)

    assert_equals 3 "$count"
}

function test_extract_review_items_extracts_high_severity() {
    local review_body='## AI Code Review

### Issues
1. [HIGH] [security] src/auth.rs:45: SQL injection
'

    local result
    result=$(echo "$review_body" | python3 "${LIB_DIR}/extract_review_items.py")

    local contains
    contains=$(echo "$result" | grep -c '^1|HIGH|security|' || true)
    assert_equals 1 "$contains"
}

function test_extract_review_items_extracts_medium_and_architecture() {
    local review_body='## AI Code Review

### Issues
2. [MEDIUM] [architecture] src/db.rs:20: Tight coupling
'

    local result
    result=$(echo "$review_body" | python3 "${LIB_DIR}/extract_review_items.py")

    local contains
    contains=$(echo "$result" | grep -c '^2|MEDIUM|architecture|' || true)
    assert_equals 1 "$contains"
}

function test_extract_review_items_location_format() {
    local review_body='## AI Code Review

### Issues
1. [LOW] [quality] scripts/lib/extract_review_items.py:85: Magic number
'

    local result
    result=$(echo "$review_body" | python3 "${LIB_DIR}/extract_review_items.py")

    local has_location
    has_location=$(echo "$result" | grep -c 'scripts/lib/extract_review_items.py:85' || true)
    assert_equals 1 "$has_location"
}

function test_extract_review_items_severity_not_in_location() {
    local review_body='## AI Code Review

### Issues
1. [LOW] [quality] src/file.rs:10: Some issue
'

    local result
    result=$(echo "$review_body" | python3 "${LIB_DIR}/extract_review_items.py")

    local has_low_in_location
    has_low_in_location=$(echo "$result" | grep -c '^1|LOW|quality|LOW|' || true)
    assert_equals 0 "$has_low_in_location"
}

function test_parse_issue_command_create_issue_for() {
    local result
    result=$(echo "create issue for 1, 2, 3" | python3 "${LIB_DIR}/parse_issue_command.py")

    assert_equals "1,2,3" "$result"
}

function test_parse_issue_command_shorthand() {
    local result
    result=$(echo "issue 5" | python3 "${LIB_DIR}/parse_issue_command.py")

    assert_equals "5" "$result"
}

function test_parse_issue_command_uppercase() {
    local result
    result=$(echo "CREATE ISSUE FOR 1 2" | python3 "${LIB_DIR}/parse_issue_command.py")

    assert_equals "1,2" "$result"
}

function test_parse_issue_command_non_command() {
    local result
    result=$(echo "This is a regular comment" | python3 "${LIB_DIR}/parse_issue_command.py")

    assert_equals "" "$result"
}

function test_get_pr_reviews_returns_most_recent() {
    local json='[
        {"id": 1, "state": "approved", "created_at": "2024-01-01T00:00:00Z", "body": "Old review"},
        {"id": 2, "state": "changes_requested", "created_at": "2024-01-02T00:00:00Z", "body": "Newer review"}
    ]'

    local result
    result=$(echo "$json" | python3 "${LIB_DIR}/get_pr_reviews.py")

    local contains
    contains=$(echo "$result" | grep -c 'Newer review' || true)
    assert_equals 1 "$contains"
}

function test_get_pr_reviews_contains_correct_id_and_state() {
    local json='[
        {"id": 1, "state": "approved", "created_at": "2024-01-01T00:00:00Z", "body": "Old review"},
        {"id": 2, "state": "changes_requested", "created_at": "2024-01-02T00:00:00Z", "body": "Newer review"}
    ]'

    local result
    result=$(echo "$json" | python3 "${LIB_DIR}/get_pr_reviews.py")

    local contains
    contains=$(echo "$result" | grep -c '2|changes_requested' || true)
    assert_equals 1 "$contains"
}

function test_get_pr_comments_parses_two_comments() {
    local json='[
        {"id": 100, "created_at": "2024-01-01T00:00:00Z", "body": "First comment"},
        {"id": 101, "created_at": "2024-01-02T00:00:00Z", "body": "Second comment"}
    ]'

    local result
    result=$(echo "$json" | python3 "${LIB_DIR}/get_pr_comments.py")

    local count
    count=$(echo "$result" | wc -l)

    assert_equals 2 "$count"
}

function test_get_pr_comments_parses_correctly() {
    local json='[
        {"id": 100, "created_at": "2024-01-01T00:00:00Z", "body": "First comment"}
    ]'

    local result
    result=$(echo "$json" | python3 "${LIB_DIR}/get_pr_comments.py")

    local contains
    contains=$(echo "$result" | grep -c '100.*First comment' || true)
    assert_equals 1 "$contains"
}

function test_json_escape_escapes_quotes() {
    local result
    result=$(printf 'Hello "world"' | python3 "${LIB_DIR}/json_escape.py")

    assert_equals '"Hello \"world\""' "$result"
}

function test_python_files_use_snake_case() {
    local expected_files="build_comment.py build_prompt.py extract_review_items.py get_pr_comments.py get_pr_reviews.py json_escape.py parse_issue_command.py"
    local all_found=1
    
    for file in $expected_files; do
        if [[ ! -f "${LIB_DIR}/${file}" ]]; then
            all_found=0
        fi
    done
    
    assert_equals 1 "$all_found"
}