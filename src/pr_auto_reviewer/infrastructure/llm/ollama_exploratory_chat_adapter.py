"""DEPRECATED: Staged multi-phase code review via Ollama chat API with exploration tools.

This adapter has been replaced by the agentic review architecture:
- OllamaAgentAdapter (infrastructure/llm/ollama_agent_adapter.py)
- AgentConversationService (application/services/agent_conversation_service.py)
- MultiPhaseReviewOrchestrator (application/services/multi_phase_review_orchestrator.py)
- TurnParser (application/services/turn_parser.py)
- FindingAggregator (application/services/finding_aggregator.py)

Kept for backward compatibility with existing tests. Do NOT add new features.
"""

from __future__ import annotations

import json
import logging
import tempfile
import time
from pathlib import Path
from dataclasses import dataclass
from typing import Any, ClassVar
import requests

from pr_auto_reviewer.domain.agent.phase_result import PhaseResult
from pr_auto_reviewer.application.ports.outbound.llm_review_port import (
    LlmReviewPort,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.entities.review_praise import ReviewPraise
from pr_auto_reviewer.domain.entities.review_suggestion import (
    ReviewSuggestion,
)
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import (
    ComposedPrompt,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.review_verdict import (
    ReviewVerdict,
)
from pr_auto_reviewer.infrastructure.llm.exploration_tool_service import (
    ExplorationToolService,
)
from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)
from pr_auto_reviewer.infrastructure.review_publishers._shared import (
    ReasonBuilder,
)
from pr_auto_reviewer.domain.services.review_item_factory import (
    ReviewItemFactory,
)

logger = logging.getLogger(__name__)

_PHASE_PROMPT_DIR = (
    Path(__file__).resolve().parent.parent
    / "fragments"
    / "content"
    / "universal"
)

_PHASES: list[tuple[str, str]] = [
    ("bug-hunt-diff", "Bug Hunt — Diff"),
    ("bug-hunt-branch", "Bug Hunt — Branch"),
    ("architecture-review", "Architecture Review"),
]

_METHODOLOGY = (
    "\n## ANTI-HALLUCINATION RULES\n\n"
    "Before identifying any issue in a file, you MUST read that file first.\n"
    "Never reference a file path or symbol you have not confirmed exists\n"
    "via read_file, search_codebase, or list_directory.\n"
    "Every finding MUST be grounded in code you actually observed.\n"
    "If a tool returns an error (e.g. file not found, permission denied),\n"
    "do NOT report that error as a finding. Either retry with a corrected\n"
    "path or skip the file entirely. Tool errors are not code issues.\n"
    "If the repository appears to be in a language you do not understand,\n"
    "say so — never fabricate findings in a different language.\n"
    "After reading each file, describe what you observed before forming judgments.\n"
    "Only include findings whose evidence comes from code you successfully read.\n"
    "Before reporting a class as missing any method (especially __init__),\n"
    "read the superclass to verify the method is not inherited. If a class\n"
    "body is simply 'pass', it inherits all behavior from its parent —\n"
    "verify before reporting anything missing.\n"
    "Never emit a final verdict until you have inspected at least one changed\n"
    "file with the exploration tools; a verdict with zero tool calls is\n"
    "rejected and you will be asked to explore.\n"
)

_REASON_GENERATOR_PROMPT = (
    "You are a final review summarizer. Given the merged findings from "
    "a multi-phase code review below, write a single concise \"Reason\" "
    "sentence that concretely describes what the review found.\n\n"
    "The reason must:\n"
    "- Be specific: mention actual file names and the nature of each issue\n"
    "- Be concise: one sentence, ideally 10-30 words\n"
    "- NOT use abstract phrases like \"X unique findings from Y phases\"\n"
    "- Use natural language, not bullet points\n\n"
    "Example good reason:\n"
    '"Identified 3 issues: a missing shebang line in deploy.sh, an unhandled '
    'None case in parse_config(), and a hardcoded credential in auth.rs."\n\n'
    "Findings:\n"
    "{findings}\n\n"
    "Write ONLY the reason sentence. No prefixes, labels, or formatting."
)


class OllamaExploratoryChatAdapter(LlmReviewPort):
    """Staged multi-phase review using Ollama's chat API with exploration tools.

    Runs three phases in sequence:
    1. bug-hunt-diff — static diff analysis
    2. bug-hunt-branch — runtime-aware branch analysis with run_git access
    3. architecture-review — cross-file design and pattern review

    Findings from earlier phases are injected into later prompts via
    ``__PREVIOUS_FINDINGS__`` markers.
    """

    _MAX_TURNS = 10
    _MAX_EMPTY_RESPONSES = 3
    _MAX_UNPARSEABLE_RESPONSES = 3
    _MAX_FEEDBACK_ROUNDS = 2
    _VERIFY_MAX_TURNS = 5
    _FINDINGS_MARKER = "__PREVIOUS_FINDINGS__"


    _DUPLICATE_SUFFIX = ". This was previously identified but may have additional instances."

    def __init__(
        self,
        model: str,
        host: str = "http://localhost:11434",
        ollama_timeout: int = 120,
        max_retries: int = 5,
    ) -> None:
        self._model = model
        self._host = host.rstrip("/")
        self._timeout = ollama_timeout
        self._max_retries = max_retries
        self._parser = ReviewResponseParser()


    def review(self, diff: object, context: object) -> CodeReview:
        """Not used in production; raises NotImplementedError."""
        raise NotImplementedError(
            "Use review_prompt(ComposedPrompt) for staged multi-phase review"
        )

    @classmethod
    def _load_phase_prompt(cls, phase_id: str) -> str:
        """Load a phase prompt markdown file, stripping YAML frontmatter."""
        path = _PHASE_PROMPT_DIR / f"{phase_id}.md"
        raw = path.read_text()
        return ReviewResponseParser.strip_frontmatter(raw)
    @staticmethod
    def _extract_file_listing(composed_content: str) -> list[str]:
        """Extract changed file paths from the rendered prompt's diff section."""
        paths: set[str] = set()
        seen_section = False
        for line in composed_content.split("\n"):
            if line.startswith("## Diff"):
                seen_section = True
                continue
            if not seen_section:
                continue
            if line.startswith("--- a/") or line.startswith("+++ b/"):
                raw = line.split(" ", 1)[1] if " " in line else ""
                if not raw:
                    continue
                if raw == "/dev/null":
                    continue
                if raw.startswith(("a/", "b/")):
                    raw = raw[2:]
                paths.add(raw)
        return sorted(paths)

    def _run_phases_full_retry(
        self,
        repo_path: str,
        changed_files: list[str],
    ) -> CodeReview:
        """Orchestrate all review phases with full-review retry and feedback loop.

        When any phase exhausts all per-phase retries, this method catches the
        LlmUnavailableError and restarts the entire review sequence from scratch,
        injecting the valid findings accumulated so far as context.

        After all full-retry attempts, if the result still has zero items,
        additional feedback rounds feed the prior review output back to the LLM
        as context for a fresh attempt.
        """
        max_full_retries = self._max_retries
        best_attempt_items: list[ReviewItem] = []
        result: CodeReview | None = None

        for full_retry in range(max_full_retries):
            logger.info(
                "Starting full-review attempt %d/%d",
                full_retry + 1,
                max_full_retries,
            )
            attempt_items: list[ReviewItem] = []
            try:
                result = self._run_phases(repo_path, changed_files, attempt_items)
                if result.items:
                    return result
                best_attempt_items = result.items
                break
            except LlmUnavailableError as exc:
                if not self._is_max_turns_exceeded(exc):
                    raise

                if attempt_items and len(attempt_items) > len(best_attempt_items):
                    best_attempt_items = list(attempt_items)

                if full_retry == max_full_retries - 1:
                    logger.warning(
                        "All %d full-review attempts exhausted; returning findings from best attempt",
                        max_full_retries,
                    )
                    break

                logger.warning(
                    "Full-review attempt %d/%d exceeded max turns, restarting entire sequence",
                    full_retry + 1,
                    max_full_retries,
                )

        if result is None:
            if best_attempt_items:
                logger.info(
                    "Returning review with %d accumulated items after %d full retries",
                    len(best_attempt_items),
                    max_full_retries,
                )
                result = self._merge_items(best_attempt_items)
            else:
                logger.warning(
                    "No findings accumulated after %d full-review attempts",
                    max_full_retries,
                )
                result = CodeReview(
                    verdict=ReviewVerdict.APPROVED,
                    reason="No issues found across all review phases.",
                    model_used=self._model,
                )

        if not result.items:
            result = self._run_feedback_loop(repo_path, changed_files, result)

        return result


    def _run_feedback_loop(
        self,
        repo_path: str,
        changed_files: list[str],
        previous_result: CodeReview,
    ) -> CodeReview:
        """Re-run phases with the prior review output as feedback context.

        When the LLM returns zero actionable findings, the prior verdict
        and reason are serialized into a feedback prompt and passed to
        _run_phases via initial_feedback. This gives the LLM another
        chance to produce findings with the knowledge that its previous
        attempt came up empty.
        """
        best = previous_result
        for round_num in range(self._MAX_FEEDBACK_ROUNDS):
            logger.info(
                "Feedback round %d/%d: re-running with prior review context",
                round_num + 1,
                self._MAX_FEEDBACK_ROUNDS,
            )
            prior_skip_reasons = getattr(
                self, "_last_phase_skip_reasons", None
            )
            context = self._build_feedback_context(
                previous_result, round_num + 1, prior_skip_reasons
            )
            try:
                result = self._run_phases(
                    repo_path,
                    changed_files,
                    initial_feedback=context,
                )
            except LlmUnavailableError:
                logger.warning(
                    "Feedback round %d: LLM unavailable, returning best result",
                    round_num + 1,
                )
                return best
            if result.items:
                logger.info(
                    "Feedback round %d produced %d items",
                    round_num + 1,
                    len(result.items),
                )
                return result
            previous_result = result
            if len(result.summary or result.reason) > len(best.summary or best.reason):
                best = result
        logger.warning(
            "All %d feedback rounds exhausted; returning best result",
            self._MAX_FEEDBACK_ROUNDS,
        )
        return best

    @staticmethod
    def _build_feedback_context(
        result: CodeReview,
        round_number: int,
        skip_reasons: list[str] | None = None,
    ) -> str:
        """Build a feedback prompt from a zero-item review result.

        Each successive round escalates urgency so the LLM knows this
        is a repeated failure, not a one-off retry.
        """
        escalation = (
            "This is unusual for a real code change — please re-examine "
            "the diff more carefully."
            if round_number == 1
            else (
                f"This is your {round_number}{'st' if round_number == 1 else 'nd'} attempt. Every prior attempt "
                "also found nothing actionable. Re-examine with fresh eyes: "
                "assume the diff contains issues and dig deeper."
            )
        )
        skip_note = ""
        if skip_reasons:
            unique = sorted(set(skip_reasons))
            skip_note = (
                "\n\nItems you reported in the previous attempt were dropped "
                "for these reasons (fix them in this attempt):\n"
                + "\n".join(f"- {r}" for r in unique)
            )
        return (
            f"## Review Feedback — Attempt #{round_number} Returned No Findings\n\n"
            "Your previous review of this pull request produced **zero** actionable findings. "
            f"{escalation}"
            f"{skip_note}\n\n"
            f"Previous verdict: **{result.verdict.value}** — "
            f"{result.summary or result.reason or 'no explanation provided'}\n\n"
            "Look for genuine issues: bugs, logic errors, security problems, "
            "performance concerns, API misuse, race conditions, missing edge cases, "
            "and architectural problems. Only report issues you can confirm by "
            "reading the affected files.\n\n"
            "If after careful re-examination you truly find no issues, "
            "explain why the change is correct."
        )
    def _run_phases(
        self,
        repo_path: str,
        changed_files: list[str],
        accumulated_items: list[ReviewItem] | None = None,
        initial_feedback: str = "",
    ) -> CodeReview:
        """Orchestrate all review phases, merging results.

        If accumulated_items is provided, it is populated in-place as each
        phase completes so callers can recover partial results after an
        LlmUnavailableError terminates mid-sequence.
        """

        all_items: list[ReviewItem] = []
        all_skip_reasons: list[str] = []
        last_phase_result: PhaseResult | None = None
        previous_findings: str = ""

        for phase_id, phase_name in _PHASES:
            logger.info("Starting phase: %s", phase_name)
            phase_prompt = _METHODOLOGY + "\n\n" + self._load_phase_prompt(phase_id)

            if initial_feedback:
                phase_prompt = initial_feedback + "\n\n" + phase_prompt
                initial_feedback = ""

            if self._FINDINGS_MARKER in phase_prompt:
                phase_prompt = phase_prompt.replace(
                    self._FINDINGS_MARKER,
                    previous_findings or "No findings from prior phases.",
                )

            phase_result = self._run_phase_with_retry(
                phase_name=phase_name,
                phase_prompt=phase_prompt,
                repo_path=repo_path,
                changed_files=changed_files,
            )
            all_items.extend(phase_result.items)
            all_skip_reasons.extend(phase_result.skip_reasons)
            last_phase_result = phase_result
            if accumulated_items is not None:
                accumulated_items.clear()
                accumulated_items.extend(all_items)
            previous_findings = json.dumps(
                [
                    {
                        "file": item.file_path,
                        "severity": str(item.severity),
                        "category": str(item.category),
                        "description": item.description,
                    }
                    for item in all_items
                ],
                indent=2,
            )
            logger.info(
                "Phase %s complete: %d findings (total: %d)",
                phase_name,
                len(phase_result.items),
                len(all_items),
            )

        self._last_phase_skip_reasons = all_skip_reasons
        if not all_items:
            verdict = ReviewVerdict.APPROVED
            reason = "No issues found across all review phases."
            summary = ""
            suggestions: list[ReviewSuggestion] = []
            praise_list: list[ReviewPraise] = []

            if last_phase_result is not None:
                if last_phase_result.llm_verdict is not None:
                    try:
                        verdict = ReviewVerdict(last_phase_result.llm_verdict)
                    except ValueError:
                        pass
                if last_phase_result.llm_reason:
                    reason = last_phase_result.llm_reason
                if last_phase_result.llm_summary:
                    summary = last_phase_result.llm_summary
                for s in last_phase_result.llm_suggestions:
                    suggestions.append(ReviewSuggestion(
                        file=s.get("file", ""),
                        line=s.get("line", ""),
                        description=s.get("description", ""),
                    ))
                for p in last_phase_result.llm_praise:
                    praise_list.append(ReviewPraise(
                        file=p.get("file", ""),
                        description=p.get("description", ""),
                    ))

            return CodeReview(
                verdict=verdict,
                reason=reason,
                summary=summary,
                suggestions=suggestions,
                praise=praise_list,
                model_used=self._model,
            )

        return self._verify_and_rebuild(self._merge_items(all_items, last_phase_result), repo_path, changed_files)


    def review_prompt(self, prompt: ComposedPrompt) -> CodeReview:
        """Run all review phases against the composed prompt's repository."""
        repo_path = prompt.repo_path
        if not repo_path or not repo_path.strip():
            raise ValueError(
                "repo_path is required for staged multi-phase review"
            )
        changed_files = self._extract_file_listing(prompt.content)
        return self._run_phases_full_retry(repo_path.strip(), changed_files)


    def _run_phase_with_retry(
        self,
        phase_name: str,
        phase_prompt: str,
        repo_path: str,
        changed_files: list[str],
    ) -> PhaseResult:
        tool_service = ExplorationToolService(repo_path, changed_files=changed_files)
        for retry in range(self._max_retries):
            try:
                return self._run_conversation(
                    system_prompt=phase_prompt,
                    repo_path=repo_path,
                    tool_service=tool_service,
                    changed_files=changed_files,
                )
            except LlmUnavailableError as exc:
                if not self._is_max_turns_exceeded(exc):
                    raise
                if retry == self._max_retries - 1:
                    raise
                logger.warning(
                    "Phase %s exceeded max turns (attempt %d/%d), restarting",
                    phase_name,
                    retry + 1,
                    self._max_retries,
                )
                tool_service = ExplorationToolService(repo_path, changed_files=changed_files)
        raise RuntimeError("Unreachable: _max_retries must be >= 1")

    @staticmethod
    def _is_max_turns_exceeded(exc: LlmUnavailableError) -> bool:
        return "Phase exceeded max turns" in str(exc)

    def _run_conversation(
        self,
        system_prompt: str,
        repo_path: str,
        tool_service: ExplorationToolService,
        changed_files: list[str],
    ) -> PhaseResult:
        """Run a single-phase multi-turn conversation with tool access."""
        file_listing = "\n  - ".join(changed_files) if changed_files else "(none)"
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Changed files for this review:\n"
                    f"  - {file_listing}\n\n"
                    f"Repository path: {repo_path}\n\n"
                    "Use get_changed_files to see which files were modified, "
                    "then use read_file to inspect relevant files.\n"
                    "You have access to read_file, search_codebase, "
                    "list_directory, run_git, and get_changed_files tools.\n"
                    "When you have completed your review for this phase, "
                    'respond with a JSON object containing "verdict", '
                    '"reason", "suggestions", "praise", and "items" keys.\n'
                    "For tool calls, respond with a JSON object containing "
                    '"action" and "args" keys.'
                ),
            },
        ]

        empty_consecutive = 0
        unparseable_consecutive = 0
        tool_calls = 0
        for turn in range(self._MAX_TURNS):
            logger.debug("Turn %d/%d", turn + 1, self._MAX_TURNS)
            content = self._stream_chat(messages)
            if not content:
                empty_consecutive += 1
                if empty_consecutive >= self._MAX_EMPTY_RESPONSES:
                    raise LlmUnavailableError(
                        f"LLM returned empty response {empty_consecutive} "
                        f"consecutive times at turn {turn + 1}"
                    )
                logger.debug(
                    "Empty response at turn %d; reprompting",
                    turn + 1,
                )
                messages.append({
                    "role": "user",
                    "content": (
                        "Your previous response was empty. Please continue "
                        "your analysis or provide your review findings as "
                        'a JSON object with "verdict", "reason", '
                        '"suggestions", "praise", and "items" keys.'
                    ),
                })
                continue

            empty_consecutive = 0

            parsed = self._parse_turn(content, repo_path)
            if parsed is None:
                unparseable_consecutive += 1
                if unparseable_consecutive >= self._MAX_UNPARSEABLE_RESPONSES:
                    raise LlmUnavailableError(
                        f"LLM returned unparseable response "
                        f"{unparseable_consecutive} consecutive times "
                        f"at turn {turn + 1}"
                    )
                logger.debug(
                    "Unparseable response at turn %d; reprompting",
                    turn + 1,
                )
                messages.append({
                    "role": "user",
                    "content": (
                        "Your previous response was not valid JSON. Please "
                        "respond with a JSON object containing either "
                        "'action' and 'args' for tool calls, or 'verdict', "
                        "'reason', 'suggestions', 'praise', and 'items' "
                        "for your final review findings."
                    ),
                })
                continue
            unparseable_consecutive = 0

            messages.append({"role": "assistant", "content": content})

            if isinstance(parsed, PhaseResult):
                if tool_calls > 0:
                    logger.debug("Got verdict at turn %d", turn + 1)
                    return parsed
                logger.debug(
                    "Verdict at turn %d with no tool exploration; demanding exploration",
                    turn + 1,
                )
                messages.append({
                    "role": "user",
                    "content": (
                        "You reached a verdict without inspecting the repository. "
                        "Before concluding, you MUST use the exploration tools "
                        "(read_file, search_codebase, list_directory, run_git) "
                        "to inspect the changed files. Do that now, then provide "
                        "your final JSON verdict."
                    ),
                })
                continue

            action = parsed["action"]
            args = parsed.get("args", "")
            logger.debug(
                "Tool call — action=%s args=%s",
                action,
                str(args)[:200],
            )
            result = tool_service.execute(action, args)
            tool_calls += 1
            result_truncated = json.dumps(result)[:300]
            logger.debug(
                "Tool result (%d chars): %s",
                len(json.dumps(result)),
                result_truncated,
            )
            messages.append({
                "role": "user",
                "content": json.dumps(result),
            })

        fd, dump_path = tempfile.mkstemp(
            prefix="pr-review-exhausted-",
            suffix=".json",
        )
        with open(fd, "w") as f:
            json.dump(messages, f, indent=2, default=str)
        raise LlmUnavailableError(
            f"Phase exceeded max turns ({self._MAX_TURNS}) without a verdict. "
            f"Full conversation dumped to {dump_path}"
        )

    def _merge_items(
        self,
        items: list[ReviewItem],
        phase_result: PhaseResult | None = None,
    ) -> CodeReview:
        """Deduplicate and merge items across phases into a CodeReview.

        When ``phase_result`` is provided, its ``llm_reason`` is used as
        a fallback when the merged item list is empty, and its
        ``llm_suggestions`` / ``llm_praise`` are parsed into the
        corresponding domain entities.
        """
        seen: set[tuple[str, str, str, str]] = set()
        merged: list[ReviewItem] = []

        for item in items:
            desc = item.description
            if desc.endswith(self._DUPLICATE_SUFFIX):
                desc = desc[: -len(self._DUPLICATE_SUFFIX)]
            key = (
                item.file_path or "",
                str(item.severity),
                str(item.category),
                desc,
            )
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)

        for i, item in enumerate(merged, 1):
            object.__setattr__(item, "number", i)
        has_blocking = any(item.severity.is_blocking for item in merged)
        verdict = (
            ReviewVerdict.CHANGES_REQUESTED
            if has_blocking
            else ReviewVerdict.APPROVED
        )

        reason = ReasonBuilder.build(merged)
        summary = ""
        suggestions: list[ReviewSuggestion] = []
        praise: list[ReviewPraise] = []

        if phase_result is not None:
            if phase_result.llm_verdict is not None:
                try:
                    verdict = ReviewVerdict(phase_result.llm_verdict)
                except ValueError:
                    pass
            if not reason and phase_result.llm_reason:
                reason = phase_result.llm_reason
            if phase_result.llm_summary:
                summary = phase_result.llm_summary
            for s in phase_result.llm_suggestions:
                suggestions.append(ReviewSuggestion(
                    file=s.get("file", ""),
                    line=s.get("line", ""),
                    description=s.get("description", ""),
                ))
            for p in phase_result.llm_praise:
                praise.append(ReviewPraise(
                    file=p.get("file", ""),
                    description=p.get("description", ""),
                ))

        return CodeReview(
            verdict=verdict,
            reason=reason,
            summary=summary,
            items=merged,
            suggestions=suggestions,
            praise=praise,
            model_used=self._model,
        )
    def _run_verification_conversation(
        self,
        system_prompt: str,
        repo_path: str,
        tool_service: ExplorationToolService,
    ) -> list[dict[str, Any]] | None:
        """Run a multi-turn verification conversation with tool access.

        Returns parsed verification results (list of {finding_index, verified, reason})
        on success, or None if verification failed to produce parseable output.
        """
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Repository path: {repo_path}\n\n"
                    "Verify each finding above against the ACTUAL source code. "
                    "Use read_file to inspect files, search_codebase to locate "
                    "symbols, and list_directory to explore the repository. "
                    "You have access to read_file, search_codebase, "
                    "list_directory, run_git, and get_changed_files tools.\n\n"
                    "For tool calls, respond with a JSON object containing "
                    "'action' and 'args' keys.\n"
                    "When verification is complete, respond with a JSON object "
                    "containing a 'results' array."
                ),
            },
        ]

        empty_consecutive = 0
        unparseable_consecutive = 0
        for turn in range(self._VERIFY_MAX_TURNS):
            logger.debug(
                "Verify turn %d/%d",
                turn + 1,
                self._VERIFY_MAX_TURNS,
            )
            content = self._stream_chat(messages)
            if not content:
                empty_consecutive += 1
                if empty_consecutive >= self._MAX_EMPTY_RESPONSES:
                    logger.warning(
                        "Verification: %d consecutive empty responses; "
                        "aborting",
                        empty_consecutive,
                    )
                    return None
                logger.debug(
                    "Empty response at verify turn %d; reprompting",
                    turn + 1,
                )
                messages.append({
                    "role": "user",
                    "content": (
                        "Your previous response was empty. Please verify "
                        "each finding and respond with a JSON object "
                        "containing a 'results' array."
                    ),
                })
                continue

            empty_consecutive = 0

            parsed = self._parse_verify_turn(content)
            if parsed is None:
                unparseable_consecutive += 1
                if (
                    unparseable_consecutive
                    >= self._MAX_UNPARSEABLE_RESPONSES
                ):
                    logger.warning(
                        "Verification: %d consecutive unparseable "
                        "responses; aborting",
                        unparseable_consecutive,
                    )
                    return None
                logger.debug(
                    "Unparseable response at verify turn %d; reprompting",
                    turn + 1,
                )
                messages.append({
                    "role": "user",
                    "content": (
                        "Your previous response was not valid JSON. "
                        "Please respond with a JSON object containing "
                        "either 'action' and 'args' for tool calls, "
                        "or 'results' for your verification results."
                    ),
                })
                continue
            unparseable_consecutive = 0

            messages.append({
                "role": "assistant",
                "content": content,
            })

            if isinstance(parsed, list):
                logger.debug(
                    "Got verification results at turn %d",
                    turn + 1,
                )
                return parsed

            action = parsed["action"]
            args = parsed.get("args", "")
            logger.debug(
                "Verify tool call — action=%s args=%s",
                action,
                str(args)[:200],
            )
            result = tool_service.execute(action, args)
            result_truncated = json.dumps(result)[:300]
            logger.debug(
                "Tool result (%d chars): %s",
                len(json.dumps(result)),
                result_truncated,
            )
            messages.append({
                "role": "user",
                "content": json.dumps(result),
            })

        logger.warning(
            "Verification exceeded max turns (%d)",
            self._VERIFY_MAX_TURNS,
        )
        return None


    def _verify_and_rebuild(
        self, code_review: CodeReview, repo_path: str, changed_files: list[str]
    ) -> CodeReview:
        """Run verification on blocking findings, rebuilding CodeReview if any are dropped."""
        blocking = [i for i in code_review.items if i.severity.is_blocking]
        if not blocking:
            return code_review

        verified_items = self._verify_blocking_findings(
            code_review.items, repo_path, changed_files
        )
        if verified_items is code_review.items:
            return code_review

        for i, item in enumerate(verified_items, 1):
            object.__setattr__(item, "number", i)

        has_blocking = any(item.severity.is_blocking for item in verified_items)
        verdict = (
            ReviewVerdict.CHANGES_REQUESTED
            if has_blocking
            else ReviewVerdict.APPROVED
        )

        reason = self._generate_reason(verified_items, verdict)
        return CodeReview(
            verdict=verdict,
            reason=reason,
            items=verified_items,
            model_used=self._model,
        )

    def _verify_blocking_findings(
        self, items: list[ReviewItem], repo_path: str, changed_files: list[str]
    ) -> list[ReviewItem]:
        """Verify CRITICAL/MAJOR findings against source code, dropping hallucinations.

        Uses a multi-turn agentic conversation with tool access so the model
        can read files, search for symbols, and trace inheritance before
        confirming or rejecting each finding.
        """
        blocking = [i for i in items if i.severity.is_blocking]
        if not blocking:
            return items

        findings_text = self._format_findings_for_verification(blocking, repo_path)
        prompt = self._load_phase_prompt("verify-findings")
        prompt = prompt.replace("{findings}", findings_text)

        tool_service = ExplorationToolService(repo_path=repo_path, changed_files=changed_files)
        results = self._run_verification_conversation(
            system_prompt=prompt,
            repo_path=repo_path,
            tool_service=tool_service,
        )

        if results is None:
            logger.warning(
                "Verification failed to produce results; preserving all "
                "%d blocking findings",
                len(blocking),
            )
            return items

        verified_indices: set[int] = set()
        for r in results:
            idx = r.get("finding_index")
            if r.get("verified", False) and isinstance(idx, int):
                verified_indices.add(idx)

        verified_blocking: list[ReviewItem] = []
        for i, item in enumerate(blocking):
            if i not in verified_indices:
                continue
            item_current = item.current_code.strip()
            item_suggested = item.suggested_fix.strip()
            if item_current == item_suggested and item_current:
                logger.debug(
                    "Item %d: current_code == suggested_fix; "
                    "treating as unverified",
                    item.number,
                )
                continue
            verified_blocking.append(item)

        dropped = len(blocking) - len(verified_blocking)
        if dropped == 0:
            return items

        logger.info(
            "Verification dropped %d/%d blocking findings as hallucinations",
            dropped,
            len(blocking),
        )

        non_blocking = [i for i in items if not i.severity.is_blocking]
        return non_blocking + verified_blocking

    def _parse_verify_turn(
        self, content: str
    ) -> list[dict[str, Any]] | dict[str, str] | None:
        """Parse a verification conversation turn into results or a tool-call dict."""
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            extracted = self._parser.extract_outermost_json(content)
            if extracted is not None:
                try:
                    data = json.loads(extracted)
                except json.JSONDecodeError:
                    return None
            else:
                return None

        if not isinstance(data, dict):
            return None

        if "results" in data and isinstance(data["results"], list):
            return data["results"]

        if "action" in data and isinstance(data["action"], str):
            return data

        return None

    def _format_findings_for_verification(
        self, items: list[ReviewItem], repo_path: str
    ) -> str:
        """Format blocking findings with surrounding file context for verification."""
        parts: list[str] = []
        repo_root = Path(repo_path)

        for i, item in enumerate(items):
            file_content = ""
            if item.file_path:
                full_path = repo_root / item.file_path
                if full_path.exists():
                    file_content = self._extract_file_context(
                        full_path, item.current_code
                    )

            parts.append(
                f"## Finding {i}\n\n"
                f"- **File:** `{item.file_path or '(unknown)'}`\n"
                f"- **Severity:** {item.severity.value}\n"
                f"- **Category:** {item.category.value}\n"
                f"- **Description:** {item.description}\n"
                f"- **Current code:**\n```\n{item.current_code}\n```\n"
                f"- **Suggested fix:**\n```\n{item.suggested_fix}\n```\n"
                f"- **File content (surrounding context):**\n```\n{file_content}\n```\n"
            )

        return "\n\n".join(parts)

    @classmethod
    def _extract_file_context(cls, file_path: Path, snippet: str) -> str:
        """Extract surrounding context from a file around a matching code snippet.

        Searches for the first non-blank line of the snippet in the file using
        whitespace-normalized matching. Falls back to the first 2000 characters
        of the file if no match is found.
        """
        try:
            file_text = file_path.read_text()
        except (OSError, UnicodeDecodeError):
            return "(file could not be read)"

        if not snippet or not snippet.strip():
            return file_text[:2000]

        snippet_lines = [
            ln.strip()
            for ln in snippet.strip().split("\n")
            if ln.strip()
        ]
        if not snippet_lines:
            return file_text[:2000]

        file_lines = file_text.split("\n")
        first_snippet_line = snippet_lines[0]

        match_line = None
        for idx, line in enumerate(file_lines):
            if line.strip() == first_snippet_line:
                match_line = idx
                break

        if match_line is None:
            for idx, line in enumerate(file_lines):
                if first_snippet_line in line.strip():
                    match_line = idx
                    break

        if match_line is None:
            return file_text[:2000]

        window_start = max(0, match_line - 10)
        window_end = min(len(file_lines), match_line + 50)
        return "\n".join(file_lines[window_start:window_end])

    def _generate_reason(
        self, merged_items: list[ReviewItem], verdict: ReviewVerdict
    ) -> str:
        """Generate a concrete reason sentence from merged findings via LLM.

        Falls back to the default f-string on any error or empty response.
        """
        findings_text = "\n".join(
            f"{i+1}. [{item.file_path or '(unknown)'}] "
            f"[{item.severity.value}] "
            f"[{item.category.value}] "
            f"{item.description}"
            for i, item in enumerate(merged_items)
        )
        prompt = _REASON_GENERATOR_PROMPT.format(findings=findings_text)
        messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": "You generate concise code review reason sentences.",
            },
            {"role": "user", "content": prompt},
        ]
        try:
            reason = self._stream_chat(messages)
            reason = reason.strip().strip("\"'")
            if not reason:
                return self._default_reason(len(merged_items))
            return reason
        except LlmUnavailableError:
            logger.warning("Failed to generate reason from LLM; using fallback")
            return self._default_reason(len(merged_items))

    @staticmethod
    def _default_reason(count: int) -> str:
        return (
            f"Merged {count} unique findings from "
            f"{len(_PHASES)} review phases."
        )


    @staticmethod
    def _normalize_suggestions(raw: Any) -> list[dict[str, str]]:
        if not isinstance(raw, list):
            return []
        result: list[dict[str, str]] = []
        for entry in raw:
            if isinstance(entry, dict):
                result.append({
                    "file": str(entry.get("file", "")),
                    "line": str(entry.get("line", "")),
                    "description": str(entry.get("description", "")),
                })
            elif isinstance(entry, str):
                result.append({
                    "file": "",
                    "line": "",
                    "description": entry,
                })
        return result

    @staticmethod
    def _normalize_praise(raw: Any) -> list[dict[str, str]]:
        if not isinstance(raw, list):
            return []
        result: list[dict[str, str]] = []
        for entry in raw:
            if isinstance(entry, dict):
                result.append({
                    "file": str(entry.get("file", "")),
                    "description": str(entry.get("description", "")),
                })
            elif isinstance(entry, str):
                result.append({
                    "file": "",
                    "description": entry,
                })
        return result

    def _extract_verdict_metadata(self, content: str) -> dict[str, Any]:
        """Extract verdict metadata from a JSON block in the content.

        Returns any of verdict, reason, summary, suggestions, praise
        found in a top-level JSON object with a ``verdict`` key.
        Falls back from ``reason`` to ``summary`` when the former is
        empty.
        """
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            extracted = self._parser.extract_outermost_json(content)
            if extracted is None:
                return {}
            try:
                parsed = json.loads(extracted)
            except json.JSONDecodeError:
                return {}
        if isinstance(parsed, dict) and "verdict" in parsed:
            return {
                "verdict": str(parsed.get("verdict", "")),
                "reason": str(parsed.get("reason") or parsed.get("summary", "")),
                "summary": str(parsed.get("summary", "")),
                "suggestions": self._normalize_suggestions(parsed.get("suggestions", [])),
                "praise": self._normalize_praise(parsed.get("praise", [])),
            }
        return {}
    def _parse_turn(self, content: str, repo_path: str
    ) -> PhaseResult | dict[str, str] | None:
        """Parse a conversation turn into a ``PhaseResult`` or tool-call dict.

        Returns a ``PhaseResult`` when items or a verdict are present,
        a ``{"action": ..., "args": ...}`` dict for a tool call, or
        ``None`` when the content is not parseable.
        """
        items = self._parser.parse_items(content)
        if items:
            review_items, skip_reasons = ReviewItemFactory().create(items, repo_path, [])
            metadata = self._extract_verdict_metadata(content)
            return PhaseResult(
                items=review_items,
                llm_verdict=metadata.get("verdict") or None,
                llm_reason=metadata.get("reason", ""),
                llm_summary=metadata.get("summary", ""),
                llm_suggestions=metadata.get("suggestions", []),
                llm_praise=metadata.get("praise", []),
                skip_reasons=skip_reasons,
            )
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError:
            extracted = self._parser.extract_outermost_json(content)
            if extracted is not None:
                try:
                    parsed = json.loads(extracted)
                except json.JSONDecodeError:
                    logger.debug("Failed to parse turn content as JSON.")
                    return None
            else:
                logger.debug("Failed to parse turn content as JSON.")
                return None
        if isinstance(parsed, list):
            return PhaseResult()
        if isinstance(parsed, dict) and "action" in parsed:
            raw_args = parsed.get("args", "")
            if isinstance(raw_args, list):
                args = " ".join(str(a) for a in raw_args)
            elif isinstance(raw_args, dict):
                args = self._extract_dict_args(
                    str(parsed["action"]), raw_args
                )
            else:
                args = str(raw_args)
            return {"action": str(parsed["action"]), "args": args}

        if isinstance(parsed, dict) and "verdict" in parsed:
            items_data = (
                parsed.get("items")
                or parsed.get("issues")
                or parsed.get("findings")
                or []
            )
            llm_verdict = str(parsed.get("verdict", ""))
            llm_reason = str(parsed.get("reason") or parsed.get("summary", ""))
            llm_summary = str(parsed.get("summary", ""))
            llm_suggestions = self._normalize_suggestions(parsed.get("suggestions", []))
            llm_praise = self._normalize_praise(parsed.get("praise", []))
            review_items, skip_reasons = ReviewItemFactory().create(items_data, repo_path, [])
            return PhaseResult(
                items=review_items,
                llm_verdict=llm_verdict,
                llm_reason=llm_reason,
                llm_summary=llm_summary,
                llm_suggestions=llm_suggestions,
                llm_praise=llm_praise,
                skip_reasons=skip_reasons,
            )
        return None

    _DICT_ARG_KEYS: ClassVar[dict[str, list[str]]] = {
        "read_file": ["file", "file_path"],
        "list_directory": ["path", "directory_path"],
        "search_codebase": ["pattern"],
        "run_git": ["command"],
    }

    def _extract_dict_args(
        self, action: str, raw_args: dict[str, Any]
    ) -> str:
        """Extract args from dict-format tool calls the LLM sometimes sends."""
        for key in self._DICT_ARG_KEYS.get(action, []):
            if key in raw_args:
                return str(raw_args[key])
        for fallback in (
            "command", "path", "pattern", "file", "file_path",
            "directory_path", "query",
        ):
            if fallback in raw_args:
                return str(raw_args[fallback])
        return str(raw_args)

    def _stream_chat(self, messages: list[dict[str, Any]]) -> str:
        """Send chat messages to Ollama and accumulate the streamed response."""
        url = f"{self._host}/api/chat"
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
        }
        for attempt in range(self._max_retries):
            try:
                http_response = requests.post(
                    url,
                    json=payload,
                    timeout=self._timeout,
                    stream=True,
                )
                http_response.raise_for_status()
                content_parts: list[str] = []
                thinking_parts: list[str] = []
                for line in http_response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        chunk: dict[str, Any] = json.loads(line)
                    except json.JSONDecodeError:
                        logger.warning(
                            "Failed to parse streaming line as JSON "
                            "(attempt %d/%d): %.300s",
                            attempt + 1,
                            self._max_retries,
                            line,
                        )
                        raise
                    message = chunk.get("message", {})
                    if isinstance(message, list):
                        for msg in message:
                            if isinstance(msg, dict):
                                content_parts.append(msg.get("content", ""))
                                thinking_parts.append(msg.get("thinking", ""))
                    else:
                        content_parts.append(message.get("content", ""))
                        thinking_parts.append(message.get("thinking", ""))
                    if chunk.get("done"):
                        break
                result = "".join(content_parts)
                if not result:
                    result = "".join(thinking_parts)
                    logger.debug(
                        "No content in response; fell back to %d chars of thinking",
                        len(result),
                    )
                logger.debug(
                    "Chat response: %d chars from %d lines, %d messages",
                    len(result),
                    len(content_parts),
                    len(messages),
                )
                return result
            except json.JSONDecodeError:
                if attempt == self._max_retries - 1:
                    raise LlmUnavailableError(
                        f"LLM chat API returned unparseable streaming "
                        f"response after {self._max_retries} attempts"
                    )
                time.sleep(2**attempt)
            except requests.RequestException as exc:
                if attempt == self._max_retries - 1:
                    raise LlmUnavailableError(
                        f"Chat request to {url} failed after "
                        f"{self._max_retries} attempts: {exc}"
                    ) from exc
                logger.warning(
                    "Chat attempt %d/%d failed, retrying...",
                    attempt + 1,
                    self._max_retries,
                )
                time.sleep(2**attempt)
        raise LlmUnavailableError("All chat requests exhausted")
