# Multi-Phase Review Execution Gaps: Resolution & Verification Report

**Date:** 2026-08-26  
**Repository:** `gbrennon/pr-auto-reviewer`  
**Pull Request Under Review:** #157 (`feat/conversation-improvement`)  
**Test Suite Status:** 2,269 passed, 0 failures, 94% line coverage  

---

## 1. Executive Summary

This report documents the systematic investigation, resolution, and verification of all five execution gaps identified during the multi-phase review sub-agent audit in `pr-auto-reviewer`.

Prior to these fixes, sub-agents exhibited:
1. **Shallow exploration & single-file bias**: Agents queried `get_changed_files` redundantly on Turn 1 or inspected only one file before concluding.
2. **Manager prompt truncation**: `PhaseManagerService` sliced `system_prompt` at character 400 (`[:400]`), cutting instructions mid-word and breaking prompt grammar.
3. **Redundant feedback cycles on clean reviews**: Clean PR reviews with zero findings triggered full re-runs without considering whether findings were refuted.
4. **Weak verifier exploration instructions**: Verifier prompts lacked explicit multi-step instructions to verify quoted snippets and rule out inherited methods or caller handling.
5. **Advisor re-prompt stalls on repeated tool calls**: Sub-agents that repeated a tool call were locked into an infinite loop if no alternative file was available because reprompts omitted explicit permission to finalize with JSON.

All five gaps have been addressed across the application layer, infrastructure templates, fragments, and test suites.

---

## 2. Taskwarrior Tasks & Acceptance Criteria Summary

Four dedicated tasks were recorded in Taskwarrior with explicit acceptance criteria and completed autonomously:

| Task ID | Description | Acceptance Criteria Status | Task Status |
|---|---|---|---|
| **Task 81 (Gap 2)** | Fix Manager Prompt Context Truncation in `PhaseManagerService` and templates | 1. `PhaseManagerService` passes complete phase instructions without arbitrary `[:400]` slicing.<br>2. `_grounding_evidence` receives full instruction context.<br>3. Unit tests verify untruncated briefing messages. | **Completed (`done`)** |
| **Task 82 (Gap 3)** | Optimize feedback loop to avoid redundant re-runs on verified clean reviews | 1. `MultiPhaseReviewOrchestratorService` handles refuted findings early without unnecessary cycles.<br>2. Clean reviews finish promptly without duplicate feedback cycles.<br>3. Full test suite passes. | **Completed (`done`)** |
| **Task 83 (Gap 4)** | Strengthen verifier exploration guidance and false-positive gating | 1. Verifier `initial_user.j2` and `explore_before_results.j2` instruct checking code snippet existence and surrounding context with tools before confirming findings.<br>2. Verifier tests updated and passing. | **Completed (`done`)** |
| **Task 84 (Gap 5)** | Enhance advisor re-prompt formatting and improved prompt propagation | 1. Advisor schema and templates format `improved_prompt` when grade is `dont_do_this`.<br>2. `MultiPhaseReviewOrchestratorService` injects advisor correction and manager replan into restarted phase.<br>3. Unit tests verify restart behavior. | **Completed (`done`)** |

---

## 3. Gap-by-Gap Resolution Details

### Gap 1: Shallow File Exploration, Single-File Bias, and Hallucinated Placeholder Paths
- **Problem**: Sub-agents queried `get_changed_files` on Turn 1 even though the files were already provided in the prompt context. Furthermore, sub-agents stopped after reading a single file, and when clean, hallucinated dummy placeholder paths (`src/main.py`, `auth.service.ts`).
- **Resolution**:
  - `initial_user.j2`: Replaced `get_changed_files` directive with explicit instruction to inspect core changed implementation files and tests using `read_file` or `search_codebase`.
  - `repeated_tool_call.j2`: Directed repeated actions toward alternate modified files or concluding.
  - `explore_before_verdict.j2`: Demanded tool exploration across changed components before rendering verdicts.
  - `_schemas.j2`: Mandated empty arrays (`"items": []`, `"suggestions": []`, `"praise": []`) on clean reviews and strictly forbade dummy placeholder paths (`src/main.py`, `path/to/file`).
  - `_METHODOLOGY` in `_core_services.py` & Phase Fragments (`bug-hunt-diff.md`, `bug-hunt-branch.md`, `architecture-review.md`): Required multi-file exploration across components.

### Gap 2: Manager Prompt Context Truncation
- **Problem**: `PhaseManagerService._grounding_evidence` and `_build_messages` sliced `next_phase.system_prompt[:400]`, causing the prompt to be chopped mid-word (`Use get_changed_files to l`, `The findi`).
- **Resolution**:
  - Removed arbitrary `[:400]` character slicing in `PhaseManagerService`.
  - Passed complete, structured `system_prompt` to `_brief_user.render()` and `_grounding_evidence()`.
  - Added unit test `test_brief_passes_untruncated_phase_instructions` in `test_phase_manager_service.py` to ensure long instruction blocks (>400 chars) are preserved in full.

### Gap 3: Feedback Loop Handling of Refuted Findings
- **Problem**: When a feedback round produced findings that were subsequently refuted by verification (`dropped_findings > 0`), the orchestrator ignored `outcome.dropped_findings` and proceeded to run additional feedback rounds.
- **Resolution**:
  - Updated `MultiPhaseReviewOrchestratorService._run_feedback_loop` to check `outcome.dropped_findings` and return immediately when verification refutes all findings, preventing wasted LLM cycles.
  - Added unit test `test_feedback_loop_returns_early_when_round_drops_all_findings` in `test_feedback_refusal_guard.py`.

### Gap 4: Strengthened Verifier Guidance & False-Positive Gating
- **Problem**: Verifier prompts were terse and did not provide clear step-by-step guidance to check snippet existence, inspect surrounding context, and rule out superclasses/mixins.
- **Resolution**:
  - Updated `src/pr_auto_reviewer/infrastructure/templates/conversation/verifier/initial_user.j2` with a 4-step checklist: inspect cited file and surrounding context, confirm quoted snippet exists, verify against superclasses/mixins, and use exploration tools.
  - Updated `explore_before_results.j2` to require tool exploration before concluding.

### Gap 5: Advisor Re-Prompt Formatting & Loop Termination
- **Problem**: On an Advisor F (`dont_do_this`), the Advisor prompt lacked clear instructions to provide actionable `improved_prompt` text. Furthermore, when an agent repeated a tool call after exploring, `repeated_tool_call.j2` omitted permission to output the JSON verdict, trapping the sub-agent in a tool retry loop until max turns.
- **Resolution**:
  - Updated `phase_grade_system.j2` to require actionable `improved_prompt` instructions when emitting `dont_do_this`.
  - Updated `repeated_tool_call.j2` to instruct: *"Inspect a different changed file from the list using read_file or search_codebase, or provide your final review JSON now if you have completed exploring the modified files."*
  - Verified that sub-agents cleanly conclude with structured JSON verdicts once exploration is finished.

---

## 4. Verification & Testing

### 4.1 Full Unit & Integration Test Suite
The full pytest suite was executed with 100% pass rate:
```
================================ test session starts ================================
TOTAL: 2,269 passed in 16.49s (94% coverage)
exit=0
```

### 4.2 Live Review Smoke Test
A live review was executed against PR #157 (`feat/conversation-improvement`) with `REVIEW_OUTPUT=terminal`:
- **Phase 1 (Bug Hunt — Diff)**: Explored modified files on Turn 1; cleanly approved with 0 false positives and 0 placeholder paths.
- **Phase 2 (Bug Hunt — Branch)**: Explored `git_platform_http_client.py` and `config.py`; approved with praise for XDG base directory conformance.
- **Phase 3 (Architecture Review)**: Executed `run_git diff --name-only` across all 25 files; when the advisor flagged a hallucinated Java inquiry with an F-grade, the Manager briefed an improved prompt, Phase 3 restarted, inspected actual files, and concluded with a clean approved verdict.
- **Publisher**: Emitted human-readable terminal review with grounded praise and suggestions.

---

## 5. Conclusion

All five sub-agent exploration, planning, grading, and verification gaps have been resolved and verified with tests and live review runs.
