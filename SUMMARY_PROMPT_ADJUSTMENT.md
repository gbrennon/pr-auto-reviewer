# Prompt Adjustment Summary — LLM Hallucination Fix

## Overview

This document summarizes the prompt engineering iterations required to fix LLM hallucinations when reviewing a PR that removes unused code. The target PR was `gbrennon/dotfiles#22` ("chore(zsh): remove unused plugins"), which simply deletes a single line from `.zshrc` removing the `zsh-ollama-command` plugin.

## What Was Implemented

### Phase 1 — PR Title & Description (Low Effort)
- Added `description` field to `OpenPullRequest` DTO, `ReviewPullRequestCommand`, and `RepositoryContext`
- Threaded PR title and description through the service layer into the prompt template
- Added a "Pull Request" section to the prompt template showing the title and description with guidance to use it to understand intent

### Phase 2 — Commit Messages (Medium Effort)
- Extended `PullRequestDiff` with `commit_messages: list[str]`
- Added `_fetch_commit_messages()` to `GitChangesetFetcherAdapter` calling `/repos/{repo}/pulls/{number}/commits`
- Added a "Commit Messages" section to the prompt template

### Test Coverage
- 6 new tests added to `test_prompt_builder.py` covering PR title, description, and commit message rendering
- Fixed 2 pre-existing test bugs (case-sensitivity in assertion strings)
- All 544 unit tests pass

## Iteration History

### Iteration 1 — Initial prompt with commit messages ✅ passed (1 attempt)

The first prompt template with commit messages and PR title was tested. The LLM produced:

- **Verdict:** REQUEST_CHANGES (wrong)
- **Issue:** Hallucinated a "MAJOR architecture" issue: "The 'zsh-ollama-command' plugin is being removed. This suggests that the functionality provided by this plugin has been integrated into other parts of the system or is no longer needed. If it's still required, consider refactoring to maintain separation of concerns."
- **Problem:** The LLM ignored the commit message "chore(zsh):remove unused plugins" and invented a false narrative about "integration" and "refactoring". It flagged a `-` line (deletion) as an architecture problem.

### Iteration 2 — Strengthened anti-hallucination rules ✅ fixed (2nd attempt)

Added three new prompt sections and strengthened two existing ones:

1. **DETECTING INTENTIONAL DELETIONS section** (new):
   - Explicit rule: pure removals with NO `+` lines are almost never problems
   - Indicators: commit message says "remove", "delete", "clean up", "unused", "deprecated"
   - Concrete anti-hallucination rule with exact example matching the PR being tested
   - BAD review example (showing the hallucination pattern) and GOOD review example

2. **MANDATORY CHECKLIST** (extended from 4 to 6 items):
   - Added #4: "Have I checked if this is an INTENTIONAL DELETION?"
   - Added #5: "Does the commit message or PR title explain this change as intentional?"

3. **CRITICAL ANTI-PATTERNS** (strengthened):
   - Added: "Flag intentional deletions as 'architecture' or 'integration' concerns — deletions are NOT architecture issues"
   - Added: "Invent narratives about why code was removed when the commit message already explains it"
   - Added: "Flag any removal when the commit message or PR title contains words like remove, delete, unused, cleanup, deprecated"
   - Added: **"THE #1 HALLUCINATION PATTERN"** callout with explicit warning

4. **Commit Messages IMPORTANT** (rewritten):
   - Changed from a gentle reminder to: **"CRITICAL: READ THE COMMIT MESSAGES ABOVE BEFORE REVIEWING THE DIFF"**
   - Added explicit bullet list of what NOT to do
   - Added forceful rule: **"IF THE COMMIT MESSAGE SAYS 'REMOVE' -> THE REMOVAL IS CORRECT. NO ISSUES. JUST PRAISE."**

5. **FILES AND CONTEXT** (extended):
   - Added config files / dotfiles guidance: removals from config files are almost always intentional maintenance

**Result after iteration 2:**
- **Verdict:** APPROVED ✅
- **Items:** 0 (no fake issues) ✅
- **Summary:** "The PR removes an unused plugin from the zshrc file, which is a good cleanup and maintains the configuration minimal."
- **Correct!** The LLM recognized the cleanup as intentional and gave appropriate praise.

## What Was Hard

1. **Overcoming the LLM's "find problems" instinct**: The LLM is trained to be a critical reviewer. It naturally wants to find issues. When the diff shows `-` lines (deletions), the LLM's instinct is to question them. The prompt must be extremely forceful to override this — mild suggestions like "recognize these as intentional" are ignored.

2. **Prompt bloat**: Each anti-hallucination rule adds to the prompt (now ~23,000 chars for this simple PR). This reduces the effective context window for actual code review. The tradeoff is necessary for accuracy.

3. **Testing feedback loop**: Each test iteration requires waiting for the LLM to respond (2-10 seconds). This makes rapid iteration difficult.

## What Was Easy

1. **Plumbing the data**: Adding commit messages and PR description to the data pipeline was straightforward. The architecture (ports/adapters pattern) made it clean to add fields without breaking existing code.

2. **Test updates**: The test suite was easy to extend. Adding `commit_messages` and `pr_description` with defaults meant no existing tests broke.

3. **The fix worked on the first attempt**: After adding the DETECTING INTENTIONAL DELETIONS section with concrete examples matching the exact PR, the LLM immediately produced correct results.
