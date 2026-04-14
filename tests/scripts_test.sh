#!/usr/bin/env bash
# Test shell scripts using bashunit

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WATCH_PRS="${SCRIPT_DIR}/watch-prs.sh"
CREATE_ISSUES="${SCRIPT_DIR}/create-issues-from-pr.sh"

function test_install_bashunit_skips_if_exists() {
    local result
    result=$(bash "${SCRIPT_DIR}/install-bashunit.sh" 2>&1)
    assert_equals 0 $?
}

function test_clean_outputs_message() {
    local result
    result=$(bash "${SCRIPT_DIR}/clean.sh" 2>&1)
    local count
    count=$(echo "$result" | grep -c 'Done' || true)
    assert_equals 1 "$count"
}

function test_clean_resets_state() {
    bash "${SCRIPT_DIR}/clean.sh" > /dev/null 2>&1
    local content
    content=$(cat "${PROJECT_DIR}/runner-data/pr-reviews.json")
    assert_equals '{"reviewed":{}}' "$content"
}

function test_list_items_requires_repo() {
    local result
    result=$(bash "${SCRIPT_DIR}/list-items.sh" 2>&1)
    assert_equals 1 $?
}

function test_list_items_requires_pr() {
    local result
    result=$(bash "${SCRIPT_DIR}/list-items.sh" owner/repo 2>&1)
    assert_equals 1 $?
}

function test_list_items_usage_message() {
    local result
    result=$(bash "${SCRIPT_DIR}/list-items.sh" 2>&1)
    local count
    count=$(echo "$result" | grep -c 'Usage:' || true)
    assert_equals 1 "$count"
}

function test_create_issue_uses_owner_token() {
    local found
    found=$(grep 'Authorization: token.*FORGEJO_TOKEN' "${WATCH_PRS}" | wc -l)
    local result=0
    if test "$found" -gt 0; then
        result=0
    else
        result=1
    fi
    assert_equals 0 "$result"
}

function test_create_issue_does_not_use_reviewer_token() {
    local found
    found=$(grep 'Authorization: token.*FORGEJO_REVIEWER_TOKEN' "${WATCH_PRS}" | wc -l)
    assert_equals 0 "$found"
}

function test_create_issues_uses_owner_token() {
    local found
    found=$(grep 'Authorization: token.*FORGEJO_TOKEN' "${CREATE_ISSUES}" | wc -l)
    local result=0
    if test "$found" -gt 0; then
        result=0
    else
        result=1
    fi
    assert_equals 0 "$result"
}

function test_create_issues_does_not_use_reviewer_token() {
    local found
    found=$(grep 'Authorization: token.*FORGEJO_REVIEWER_TOKEN' "${CREATE_ISSUES}" | wc -l)
    assert_equals 0 "$found"
}