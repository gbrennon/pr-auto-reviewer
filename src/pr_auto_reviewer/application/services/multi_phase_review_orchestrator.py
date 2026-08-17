"""MultiPhaseReviewOrchestrator — run a multi-phase review plan with retry and feedback."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from pr_auto_reviewer.application.ports.inbound.run_multi_phase_review_use_case import (
    RunMultiPhaseReviewUseCase,
)
from pr_auto_reviewer.application.ports.outbound.command_bus_port import (
    CommandBusPort,
)
from pr_auto_reviewer.domain.agent.phase_result import PhaseResult
from pr_auto_reviewer.domain.agent.review_plan import ReviewPlan
from pr_auto_reviewer.domain.agent.sub_review_guardrails import (
    SubReviewGuardrails,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.entities.review_praise import ReviewPraise
from pr_auto_reviewer.domain.entities.review_suggestion import (
    ReviewSuggestion,
)
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.domain.messages.commands.aggregate_review_findings_command import (
    AggregateReviewFindingsCommand,
)
from pr_auto_reviewer.domain.messages.commands.run_agent_conversation_command import (
    RunAgentConversationCommand,
)
from pr_auto_reviewer.domain.messages.commands.run_multi_phase_review_command import (
    RunMultiPhaseReviewCommand,
)
from pr_auto_reviewer.domain.messages.commands.verify_findings_command import (
    VerifyFindingsCommand,
)
from pr_auto_reviewer.domain.messages.events.findings_aggregated_event import (
    FindingsAggregatedEvent,
)
from pr_auto_reviewer.domain.messages.events.phase_completed_event import (
    PhaseCompletedEvent,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.review_verdict import (
    ReviewVerdict,
)

logger = logging.getLogger(__name__)

_FINDINGS_MARKER = "__PREVIOUS_FINDINGS__"


class MultiPhaseReviewOrchestrator(RunMultiPhaseReviewUseCase):
    """Orchestrate a multi-phase review plan with retry and feedback loops.

    Runs phases in sequence, injecting previous findings into later
    phases. Supports full-review retry on exhaustion and feedback loops
    when zero items are found.
    """

    _MAX_FEEDBACK_ROUNDS = 2

    def __init__(
        self,
        command_bus: CommandBusPort,
        tool_factory: Callable[[Path, list[str]], Any],
        max_retries: int = 5,
        max_feedback_rounds: int = 2,
    ) -> None:
        self._command_bus = command_bus
        self._tool_factory = tool_factory
        self._max_retries = max_retries
        self._max_feedback_rounds = max_feedback_rounds

    def execute(
        self, command: RunMultiPhaseReviewCommand
    ) -> CodeReview:
        """Execute the full review plan against *command.repo_path*."""
        return self._run_phases_full_retry(
            plan=command.plan,
            repo_path=command.repo_path,
            changed_files=command.changed_files,
            model=command.model,
        )

    def _run_phases_full_retry(
        self,
        plan: ReviewPlan,
        repo_path: Path,
        changed_files: list[str],
        model: str,
    ) -> CodeReview:
        """Orchestrate all phases with full-review retry and feedback loop."""
        best_attempt_items: list[ReviewItem] = []
        result: CodeReview | None = None

        for full_retry in range(self._max_retries):
            logger.info(
                "Starting full-review attempt %d/%d",
                full_retry + 1,
                self._max_retries,
            )
            attempt_items: list[ReviewItem] = []
            try:
                result = self._run_phases(
                    plan, repo_path, changed_files, model, attempt_items
                )
                if result.items:
                    return result
                best_attempt_items = result.items
                break
            except LlmUnavailableError as exc:
                if not self._is_max_turns_exceeded(exc):
                    raise

                if attempt_items and len(attempt_items) > len(
                    best_attempt_items
                ):
                    best_attempt_items = list(attempt_items)

                if full_retry == self._max_retries - 1:
                    logger.warning(
                        "All %d full-review attempts exhausted; "
                        "returning findings from best attempt",
                        self._max_retries,
                    )
                    break

                logger.warning(
                    "Full-review attempt %d/%d exceeded max turns, "
                    "restarting entire sequence",
                    full_retry + 1,
                    self._max_retries,
                )

        if result is None:
            if best_attempt_items:
                logger.info(
                    "Returning review with %d accumulated items after "
                    "%d full retries",
                    len(best_attempt_items),
                    self._max_retries,
                )
                result = cast(
                    CodeReview,
                    self._command_bus.dispatch(
                        AggregateReviewFindingsCommand(
                            items=best_attempt_items, model_used=model
                        )
                    ),
                )
            else:
                logger.warning(
                    "No findings accumulated after %d full-review attempts",
                    self._max_retries,
                )
                result = CodeReview(
                    verdict=ReviewVerdict.COMMENTED,
                    reason=(
                        "Application could not extract a structured verdict "
                        "from any review phase."
                    ),
                    summary=(
                        f"Reviewed {len(plan.phases)} phases over model {model}; "
                        "no structured verdict or items were obtained from the "
                        "LLM output. This is a pipeline failure signal, not a "
                        "clean review."
                    ),
                    model_used=model,
                )

        if not result.items:
            result = self._run_feedback_loop(
                plan, repo_path, changed_files, model, result
            )

        return result

    def _run_feedback_loop(
        self,
        plan: ReviewPlan,
        repo_path: Path,
        changed_files: list[str],
        model: str,
        previous_result: CodeReview,
    ) -> CodeReview:
        """Re-run phases with the prior review output as feedback context."""
        best = previous_result
        for round_num in range(self._max_feedback_rounds):
            logger.info(
                "Feedback round %d/%d: re-running with prior review context",
                round_num + 1,
                self._max_feedback_rounds,
            )
            context = self._build_feedback_context(
                previous_result, round_num + 1
            )
            try:
                result = self._run_phases(
                    plan,
                    repo_path,
                    changed_files,
                    model,
                    initial_feedback=context,
                )
            except LlmUnavailableError:
                logger.warning(
                    "Feedback round %d: LLM unavailable, returning best",
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
            if len(result.summary or result.reason) > len(
                best.summary or best.reason
            ):
                best = result
        logger.warning(
            "All %d feedback rounds exhausted; returning best result",
            self._max_feedback_rounds,
        )
        return best

    def _build_feedback_context(
        self, result: CodeReview, round_number: int
    ) -> str:
        """Build a feedback prompt from a zero-item review result."""
        escalation = (
            "This is unusual for a real code change — please re-examine "
            "the diff more carefully."
            if round_number == 1
            else (
                f"This is your {round_number}{'st' if round_number == 1 else 'nd'} attempt. "
                "Every prior attempt also found nothing actionable. "
                "Re-examine with fresh eyes: assume the diff contains "
                "issues and dig deeper."
            )
        )
        return (
            f"## Review Feedback — Attempt #{round_number} Returned No Findings\n\n"
            "Your previous review of this pull request produced **zero** actionable findings. "
            f"{escalation}\n\n"
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
        plan: ReviewPlan,
        repo_path: Path,
        changed_files: list[str],
        model: str,
        accumulated_items: list[ReviewItem] | None = None,
        initial_feedback: str = "",
    ) -> CodeReview:
        """Orchestrate all review phases, merging results."""
        all_items: list[ReviewItem] = []
        last_phase_result: PhaseResult | None = None
        previous_findings: str = ""

        for phase in plan.phases:
            logger.info("Starting phase: %s", phase.phase_name)
            phase_prompt = (
                plan.methodology + "\n\n" + phase.system_prompt
            )

            if initial_feedback:
                phase_prompt = initial_feedback + "\n\n" + phase_prompt
                initial_feedback = ""

            if _FINDINGS_MARKER in phase_prompt:
                phase_prompt = phase_prompt.replace(
                    _FINDINGS_MARKER,
                    previous_findings or "No findings from prior phases.",
                )

            phase_result = self._run_phase_with_retry(
                phase_name=phase.phase_name,
                phase_prompt=phase_prompt,
                repo_path=repo_path,
                changed_files=changed_files,
            )
            existing_keys = {
                (item.file_path or "", item.description)
                for item in all_items
            }
            new_count = 0
            for item in phase_result.items:
                key = (item.file_path or "", item.description)
                if key not in existing_keys:
                    all_items.append(item)
                    existing_keys.add(key)
                    new_count += 1
            if new_count < len(phase_result.items):
                logger.info(
                    "Phase %s: %d/%d items were duplicates of prior phases",
                    phase.phase_name,
                    len(phase_result.items) - new_count,
                    len(phase_result.items),
                )
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
            self._publish(PhaseCompletedEvent(
                phase_name=phase.phase_name,
                phase_result=phase_result,
                total_findings=len(all_items),
            ))
            logger.info(
                "Phase %s complete: %d findings (total: %d)",
                phase.phase_name,
                len(phase_result.items),
                len(all_items),
            )

        if not all_items:
            verdict = ReviewVerdict.COMMENTED
            reason = "No issues found across all review phases."
            summary = "No issues found across all review phases."
            suggestions: list[ReviewSuggestion] = []
            praise_list: list[ReviewPraise] = []

            if last_phase_result is not None:
                coerced = ReviewVerdict.coerce(
                    last_phase_result.llm_verdict
                )
                if coerced is not None and coerced is not ReviewVerdict.COMMENTED:
                    verdict = coerced
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

            if verdict == ReviewVerdict.COMMENTED:
                if not reason:
                    reason = (
                        "Application could not extract a structured verdict "
                        "from any review phase."
                    )
                summary = (
                    f"Reviewed {len(plan.phases)} phases over model {model}; "
                    "no structured verdict or items were obtained from the "
                    "LLM output. This is a pipeline failure signal, not a "
                    "clean review."
                )
            else:
                if not reason:
                    reason = "Review completed without action items."
                if not summary:
                    summary = reason

            return CodeReview(
                verdict=verdict,
                reason=reason,
                summary=summary,
                suggestions=suggestions,
                praise=praise_list,
                model_used=model,
            )

        code_review = self._command_bus.dispatch(
            AggregateReviewFindingsCommand(
                items=all_items,
                phase_result=last_phase_result,
                model_used=model,
            )
        )
        if code_review.items:
            verified_items = self._command_bus.dispatch(
                VerifyFindingsCommand(
                    items=code_review.items,
                    repo_path=repo_path,
                    changed_files=changed_files,
                )
            )
            if (
                verified_items is not None
                and verified_items is not code_review.items
            ):
                code_review = self._rebuild_after_verification(
                    verified_items, model, previous=code_review,
                )
        self._publish(FindingsAggregatedEvent(code_review=code_review))
        return code_review

    def _rebuild_after_verification(
        self, verified_items: list[Any], model: str,
        previous: CodeReview | None = None,
    ) -> CodeReview:
        """Rebuild a CodeReview after verification dropped some items."""
        previous_items = len(previous.items) if previous is not None else 0

        review_items = [
            item for item in verified_items if isinstance(item, ReviewItem)
        ]
        if previous is not None and previous.verdict == ReviewVerdict.COMMENTED:
            verdict = ReviewVerdict.COMMENTED
        else:
            verdict = SubReviewGuardrails().verdict_for(review_items)

        dropped = previous_items - len(review_items)
        if dropped and previous is not None:
            reason = (
                f"{dropped} finding(s) dropped because they did not survive "
                "verification against source code."
            )
            summary = (
                f"{dropped} of {previous_items} findings did not survive "
                "verification against source code."
            )
        else:
            summary = (
                previous.summary
                if previous is not None and previous.summary
                else (
                    f"Reviewed the diff over model {model}; "
                    "no actionable findings remained after verification."
                )
            )
            reason = (
                previous.reason
                if previous is not None and previous.reason
                else "Findings verified against source code."
            )
        suggestions = (previous.suggestions if previous is not None else [])
        praise = (previous.praise if previous is not None else [])

        return CodeReview(
            verdict=verdict,
            reason=reason,
            summary=summary,
            items=review_items,
            suggestions=list(suggestions),
            praise=list(praise),
            model_used=model,
        )

    def _run_phase_with_retry(
        self,
        phase_name: str,
        phase_prompt: str,
        repo_path: Path,
        changed_files: list[str],
    ) -> PhaseResult:
        """Run a single phase with per-phase retry on exhaustion."""
        tool_service = self._tool_factory(
            repo_path, changed_files
        )
        for retry in range(self._max_retries):
            try:
                return self._command_bus.dispatch(
                    RunAgentConversationCommand(
                        system_prompt=phase_prompt,
                        repo_path=repo_path,
                        changed_files=changed_files,
                        tool_execution=tool_service,
                        phase_name=phase_name,
                    )
                )
            except LlmUnavailableError as exc:
                if not self._is_max_turns_exceeded(exc):
                    raise
                if retry == self._max_retries - 1:
                    raise
                logger.warning(
                    "Phase %s exceeded max turns (attempt %d/%d), "
                    "restarting",
                    phase_name,
                    retry + 1,
                    self._max_retries,
                )
                tool_service = self._tool_factory(
                    repo_path, changed_files
                )
        raise RuntimeError("Unreachable: _max_retries must be >= 1")

    def _is_max_turns_exceeded(self, exc: LlmUnavailableError) -> bool:
        return "Phase exceeded max turns" in str(exc)

    def _publish(self, event: Any) -> None:
        """Publish an event to the bus."""
        self._command_bus.dispatch(event)
