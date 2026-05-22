# Fix: LLM Hallucination About Missing Shebang

## Problem

When reviewing a bash script PR that already contained `#!/usr/bin/env bash`, the LLM
(`qwen2.5-coder:7b` at temperature 0.2) consistently hallucinated that the script was
missing a shebang line:

```
### 1. [INFO] quality (`scripts/install.sh`)

Script does not have a shebang line. It should start with '#!/usr/bin/env bash' to specify the interpreter.

### 2. [INFO] quality (`scripts/install.sh`)

Script does not have any comments or documentation.
```

This happened even though the diff clearly showed:

```diff
+#!/usr/bin/env bash
+set -euo pipefail
```

## Root Cause

**Two contributing factors:**

### 1. `PromptBuilder` never included `file_contents`

The `ChangesetFetcher` correctly fetched full file contents from the API and stored them
in `PullRequestDiff.file_contents`, but `PromptBuilder.build()` only appended
`diff.diff_content` to the prompt — ignoring `file_contents` entirely.

The LLM only saw unified-diff format with `+` prefixes, making it harder to parse
and easier to hallucinate formulaic feedback.

### 2. No anti-hallucination guardrails in the prompt

The GUIDELINES section had no instruction warning against generating template feedback
without verifying it against the provided code. The model was free to emit
"new script → no shebang" pattern without checking.

## Solution

### File changed: `src/pr_auto_reviewer/infrastructure/llm/prompt_builder.py`

**Change 1 — Include full file contents in prompt:**

Added a `## Full file contents` section that renders each changed file in clean
code blocks (no diff markers) before the `## Diff` section. This gives the LLM
the actual file to read, not just the diff.

```python
if diff.file_contents:
    parts.append("## Full file contents (the actual files, not diffs)")
    parts.append("")
    for file_path, content in sorted(diff.file_contents.items()):
        parts.append(f"### {file_path}")
        parts.append("```")
        parts.append(content)
        parts.append("```")
        parts.append("")
```

**Change 2 — Add explicit anti-hallucination rule:**

Added a CRITICAL guideline that explicitly warns against formulaic feedback:

```
- **CRITICAL: READ the full file contents and diff CAREFULLY
  before reporting issues.** Do NOT generate formulaic or
  template feedback (e.g. 'missing shebang', 'add comments')
  without first verifying that the problem actually exists in
  the provided code. If the code already has a shebang,
  comments, error handling, or other boilerplate, do NOT
  suggest adding them — doing so is a hallucination.
```

### File changed: `src/pr_auto_reviewer/presentation/composition_root.py`

Added `force=True` to `logging.basicConfig()` so that the `-v` / `DEBUG=1` flag
always enables debug-level logging, even if another module implicitly configured
logging earlier during imports.

## Verification

### Live testing — 5 consecutive runs

Run with: `REVIEW_OUTPUT=terminal python -m pr_auto_reviewer.cli watch-prs -r gbrennon/gb-qutebrowser --once -v`

| Run | Shebang hallucination | Items | Verdict | Notes |
|-----|----------------------|-------|---------|-------|
| 1   | ❌ Gone              | 0     | Approved | "Consider adding comments for clarity" (valid) |
| 2   | ❌ Gone              | 0     | Approved | Same consistent result |
| 3   | ❌ Gone              | 0     | Approved | Same consistent result |
| 4   | ❌ Gone              | 0     | Approved | Same consistent result |
| 5   | ❌ Gone              | 0     | Approved | Same consistent result |

**Result**: 5/5 consistent — zero shebang or boilerplate hallucinations.

### Unit tests — 4 new tests added

| Test | What it verifies |
|------|-----------------|
| `test_build_includes_file_contents_when_present` | File contents appear under `## Full file contents` header |
| `test_build_omits_file_contents_section_when_empty` | Section is absent when `file_contents` dict is empty |
| `test_build_includes_anti_hallucination_guidelines` | "missing shebang" and "hallucination" keywords in prompt |
| `test_build_file_contents_with_multiple_files` | Multiple files are all rendered with correct content |

**Full test suite**: 57/57 pass (0 failures).

## Iteration count

- **1 iteration** to identify the root cause (missing `file_contents` in prompt)
- **0 failed iterations** — the fix worked on the first attempt
- **5 verification runs** confirming consistency

**Total: 1 fix iteration + 5 verification runs = consistent success.**

## Files changed

```
src/pr_auto_reviewer/infrastructure/llm/prompt_builder.py         (+25 lines)
src/pr_auto_reviewer/presentation/composition_root.py              (+1 line, force=True)
tests/pr_auto_reviewer/infrastructure/llm/test_prompt_builder.py  (+36 lines, 4 new tests)
```

## Date

2026-05-10
