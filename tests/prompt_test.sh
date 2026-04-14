#!/usr/bin/env bash
# Test build-prompt.py using bashunit

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BUILD_PROMPT="${PROJECT_DIR}/scripts/lib/build_prompt.py"

function test_build_prompt_runs_without_error() {
    local result
    result=$(DIFF_CONTENT="test diff" python3 "${BUILD_PROMPT}" 2>&1)
    assert_equals 0 $?
}

function test_build_prompt_contains_review_priority() {
    local result
    result=$(DIFF_CONTENT="test diff" python3 "${BUILD_PROMPT}" 2>&1)
    local found
    found=$(echo "$result" | grep -c 'REVIEW PRIORITY' || true)
    assert_equals 1 "$found"
}

function test_build_prompt_contains_critical_issues() {
    local result
    result=$(DIFF_CONTENT="test diff" python3 "${BUILD_PROMPT}" 2>&1)
    local found
    found=$(echo "$result" | grep -c 'Security vulnerabilities' || true)
    assert_equals 1 "$found"
}

function test_build_prompt_contains_json_format() {
    local result
    result=$(DIFF_CONTENT="test diff" python3 "${BUILD_PROMPT}" 2>&1)
    local found
    found=$(echo "$result" | grep -c '"issues"' || true)
    assert_equals 1 "$found"
}

function test_build_prompt_contains_guidelines() {
    local result
    result=$(DIFF_CONTENT="test diff" python3 "${BUILD_PROMPT}" 2>&1)
    local found
    found=$(echo "$result" | grep -c 'GUIDELINES' || true)
    assert_equals 1 "$found"
}

function test_build_prompt_contains_no_emojis_rule() {
    local result
    result=$(DIFF_CONTENT="test diff" python3 "${BUILD_PROMPT}" 2>&1)
    local found
    found=$(echo "$result" | grep -c 'No emojis' || true)
    assert_equals 1 "$found"
}

function test_build_prompt_contains_no_comments_guideline() {
    local result
    result=$(DIFF_CONTENT="test diff" python3 "${BUILD_PROMPT}" 2>&1)
    local found
    found=$(echo "$result" | grep -c 'NEVER suggest adding comments' || true)
    assert_equals 1 "$found"
}

function test_build_prompt_contains_self_documenting_guideline() {
    local result
    result=$(DIFF_CONTENT="test diff" python3 "${BUILD_PROMPT}" 2>&1)
    local found
    found=$(echo "$result" | grep -c 'self-documenting' || true)
    assert_equals 1 "$found"
}

function test_build_prompt_includes_diff_content() {
    local result
    result=$(DIFF_CONTENT="MY_TEST_DIFF_CONTENT" python3 "${BUILD_PROMPT}" 2>&1)
    local found
    found=$(echo "$result" | grep -c 'MY_TEST_DIFF_CONTENT' || true)
    assert_equals 1 "$found"
}