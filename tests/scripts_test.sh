#!/usr/bin/env bash
# Test shell scripts using bashunit

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../scripts" && pwd)"
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

function test_test_pr_requires_repo() {
    local result
    result=$(bash "${SCRIPT_DIR}/test-pr.sh" 2>&1)
    assert_equals 1 $?
}

function test_list_items_usage_message() {
    local result
    result=$(bash "${SCRIPT_DIR}/list-items.sh" 2>&1)
    local count
    count=$(echo "$result" | grep -c 'Usage:' || true)
    assert_equals 1 "$count"
}

function test_test_pr_usage_message() {
    local result
    result=$(bash "${SCRIPT_DIR}/test-pr.sh" 2>&1)
    local count
    count=$(echo "$result" | grep -c 'Usage:' || true)
    assert_equals 1 "$count"
}