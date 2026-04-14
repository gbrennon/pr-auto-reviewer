# How to Test: Issue Creation from Review Comments

This document describes how to validate the new feature that allows creating issues from review suggestions via user commands.

## Overview

When the AI posts a review with verdict **Approved**, users can reply with a command to create issues for specific suggestions.

### Supported Command Syntax

| Command | Creates Issues For |
|---------|------------------|
| `create issue for 1, 2` | items 1 and 2 |
| `issue 1, 2` | items 1 and 2 |
| `create issue for 1` | item 1 only |
| `issue 3` | item 3 only |

> **Note:** This feature is designed to also work with GitHub in the future - the command syntax is platform-agnostic.

## Prerequisites

1. A running PR Auto Reviewer setup (or run manually with `bash scripts/watch-prs.sh`)
2. Access to a test repository with at least one open PR
3. Tokens configured properly

## Testing Steps

### Step 1: Create a Test PR with Reviewable Changes

1. Go to your test repository on Codeberg/Forgejo
2. Create a PR with sufficient code changes (for good AI review suggestions)

### Step 2: Run the Watcher

Run the watcher in single-cycle mode:

```bash
cd /home/gbrennon/Documents/repos/gbrennon/pr-auto-reviewer
bash scripts/watch-prs.sh -r owner/repo --once
```

**Expected output:**
```
=== Cycle #1 ===
Repo: owner/repo
  PR #N: [PR title]
    -> NEW/UPDATED, analyzing...
    -> Sending to Ollama...
    -> Posting review to Codeberg...
    -> Verdict: Approved
    -> Review (approved) submitted!
    -> State updated
```

### Step 3: Verify Review has Numbered Items

Check the PR review on Codeberg. You should see:

```markdown
## AI Code Review

**Verdict:** Approved

### Issues
1. [MEDIUM] [security] src/auth.rs:45: Consider using constant-time comparison

### Suggestions
2. [file:src/main.rs:10] Consider adding a unit test...
```

Note the numbers: Issue #1, Suggestion #2

### Step 4: Post a Command Comment

On the PR, add a comment with:
```
create issue for 1, 2
```

### Step 5: Run Watcher Again

```bash
bash scripts/watch-prs.sh -r owner/repo --once
```

**Expected output:**
```
=== Cycle #1 ===
Repo: owner/repo
  PR #N: [PR title]
    -> already reviewed (SHA: ...)
    -> Checking for issue creation commands...
    -> Found command in comment X: create issue for 1,2
    -> Created issue #123 for item 1
    -> Created issue #124 for item 2
```

### Step 6: Verify Issues Created

1. Check the Issues page - you should see new issues with titles like:
   - `[PR #N] 1: [MEDIUM] [security] src/auth.rs:45: Consider using constant-time comparison`
   - `[PR #N] 2: Consider adding a unit test...`

2. Check the PR comments - the app should have replied with:
   - `Created issue(s): #123, #124 from your request.`

## Test Scenarios

### Scenario 1: Invalid Item Numbers

**Setup:** Post comment `create issue for 99`

**Expected:**
- App replies with error about item 99 not existing
- No issues created

### Scenario 2: Changes Requested Verdict

**Setup:** Have a review with `changes_requested` verdict

**Expected:**
- Command `create issue for 1` should be ignored
- Log shows: `Skipping command check (verdict: changes_requested)`

### Scenario 3: Duplicate Command

**Setup:** Post the same command twice

**Expected:**
- First command creates issues
- Second command is silently ignored (tracked in state)

### Scenario 4: Mixed Valid/Invalid

**Setup:** Post `create issue for 1, 99, 2`

**Expected:**
- Error about item 99
- Issues created for items 1 and 2
- App replies with error about invalid items

## Debugging

### Enable Verbose Logging

Add `-x` to see all commands:

```bash
bash -x scripts/watch-prs.sh -r owner/repo --once 2>&1 | less
```

### Check State File

```bash
cat runner-data/pr-reviews.json | python3 -m json.tool
```

### Manual API Test

List issues:
```bash
curl -sf -H "Authorization: token $FORGEJO_TOKEN" \
  "https://codeberg.org/api/v1/repos/owner/repo/issues" | jq
```

## Cleanup

Reset test state for a PR:

```bash
# Edit runner-data/pr-reviews.json to remove the entry, or:
python3 -c "
import json
with open('runner-data/pr-reviews.json') as f:
    d = json.load(f)
# Remove specific entry
key = 'owner/repo/N'
if key in d.get('reviewed', {}):
    del d['reviewed'][key]
    with open('runner-data/pr-reviews.json', 'w') as f:
        json.dump(d, f)
"
```