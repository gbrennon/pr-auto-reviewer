from dataclasses import replace

from pr_auto_reviewer.application.ports.outbound.agent_chat_port import (
    AgentChatPort,
)
from pr_auto_reviewer.domain.value_objects.review_execution_context import (
    ReviewExecutionContext,
)

from ._shared import *
from pr_auto_reviewer.domain.services.review_item_factory import ReviewItemFactory
from .phase_run_outcome import _PhaseRunOutcome


class MultiPhaseReviewOrchestratorService(RunMultiPhaseReviewPort):
    """Orchestrate a multi-phase review plan with retry and feedback loops.

    Runs phases in sequence, injecting previous findings into later
    phases. Supports full-review retry on exhaustion and feedback loops
    when zero items are found.
    """

    _MAX_FEEDBACK_ROUNDS = 2

    def __init__(
        self,
        command_bus: CommandBusPort,
        tool_factory: Callable[[Path, list[str], str], Any],
        max_conversations: int = 48,
        max_retries: int = 5,
        max_tries: int = 2,
        max_feedback_rounds: int = 2,
        advisor: AssessPhasePort | None = None,
        manager: BriefNextPhasePort | None = None,
        chat_client: AgentChatPort | None = None,
    ) -> None:
        self._command_bus = command_bus
        self._tool_factory = tool_factory
        self._max_conversations = max_conversations
        self._max_retries = max_retries
        self._max_tries = max_tries
        self._max_feedback_rounds = max_feedback_rounds
        self._advisor = advisor
        self._manager = manager
        self._chat_client = chat_client
        self._phase_prompt_renderer = PhasePromptRenderer()
        self._conversations_started = 0
        self._correction_renderer = AdvisorCorrectionRenderer()
        self._feedback_renderer = FeedbackContextRenderer()
        self._identifier_filter = IdentifierGroundingFilterService()

    def execute(
        self, command: RunMultiPhaseReviewCommand
    ) -> CodeReview:
        """Execute the full review plan against *command.repo_path*."""
        if self._chat_client is not None:
            self._chat_client.reset_budget()
        return self._run_phases_full_retry(
            plan=command.plan,
            repo_path=command.repo_path,
            changed_files=command.changed_files,
            model=command.model,
            base_sha=command.base_sha,
            existing_item_ids=command.existing_item_ids,
            review_session=command.review_session,
            prior_items=getattr(command, "prior_items", []),
        )

    def _run_phases_full_retry(
        self,
        plan: ReviewPlan,
        repo_path: Path,
        changed_files: list[str],
        model: str,
        review_session: str,
        base_sha: str = "",
        existing_item_ids: frozenset[str] = frozenset(),
        prior_items: list[ReviewItem] | None = None,
    ) -> CodeReview:
        """Orchestrate all phases with full-review retry and feedback loop."""
        repo_name, pr_id_str = self._extract_repo_and_pr(repo_path)
        best_attempt_items: list[ReviewItem] = []
        result: CodeReview | None = None
        last_failure: Exception | None = None
        dropped_findings = 0
        self._conversations_started = 0

        for full_retry in range(self._max_retries):
            logger.info(
                "Starting full-review attempt %d/%d",
                full_retry + 1,
                self._max_retries,
            )
            attempt_items: list[ReviewItem] = []
            try:
                outcome = self._run_phases(
                    plan,
                    accumulated_items=attempt_items,
                    context=ReviewExecutionContext(
                        repo_path=repo_path,
                        changed_files=tuple(changed_files),
                        model=model,
                        base_sha=base_sha,
                        existing_item_ids=existing_item_ids,
                        pr_identifier_service=f"{repo_name}/{pr_id_str}",
                        review_session=review_session,
                        prior_items=tuple(prior_items or []),
                    ),
                )
                result = outcome.review
                dropped_findings = outcome.dropped_findings
                if outcome.has_items:
                    return result
                best_attempt_items = result.items
                break
            except ReviewBudgetExhaustedError:
                logger.warning(
                    "Conversation budget exhausted with %d findings from"
                    " this attempt; returning the best partial review",
                    len(attempt_items),
                )
                if len(attempt_items) > len(best_attempt_items):
                    best_attempt_items = list(attempt_items)
                break
            except LlmUnavailableError as exc:
                if not self._is_max_turns_exceeded(exc):
                    raise
                last_failure = exc

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
                            items=best_attempt_items,
                            model_used=model,
                            repo_name=repo_name,
                            pr_id=pr_id_str,
                            repo_path=repo_path,
                            changed_files=changed_files,
                        )
                    ),
                )
            else:
                logger.error(
                    "All %d full-review attempts exhausted with no "
                    "structured verdict and no accumulated items "
                    "(repo=%s pr=%s model=%s); refusing to publish a "
                    "COMMENTED review. Last failure: %s",
                    self._max_retries, repo_name, pr_id_str, model,
                    last_failure,
                )
                raise ReviewVerdictError(
                    "All full-review attempts exhausted without a structured "
                    "verdict or items; refusing to publish a default "
                    "COMMENTED review."
                ) from last_failure

        if not result.items:
            result = self._run_feedback_loop(
                plan, repo_path, changed_files, model, result,
                base_sha=base_sha,
                review_session=review_session,
                pr_identifier_service=f"{repo_name}/{pr_id_str}",
                existing_item_ids=existing_item_ids,
                previous_dropped_findings=dropped_findings,
            )

        return result

    def _run_feedback_loop(
        self,
        plan: ReviewPlan,
        repo_path: Path,
        changed_files: list[str],
        model: str,
        previous_result: CodeReview,
        review_session: str,
        pr_identifier_service: str,
        base_sha: str = "",
        existing_item_ids: frozenset[str] = frozenset(),
        previous_dropped_findings: int = 0,
    ) -> CodeReview:
        """Re-run the review with a progressively-improving prompt until resolved.

        After ``_max_tries`` inconclusive attempts the review is refused
        rather than publishing an unverified verdict.
        """
        evidence: list[dict[str, Any]] = []
        best = previous_result
        for attempt in range(self._max_tries):
            logger.info(
                "Re-run attempt %d/%d: improving prompt with prior results",
                attempt + 1,
                self._max_tries,
            )
            context = self._build_feedback_context(
                previous_result, attempt + 1, evidence
            )
            try:
                outcome = self._run_phases(
                    plan,
                    initial_feedback=context,
                    context=ReviewExecutionContext(
                        repo_path=repo_path,
                        changed_files=tuple(changed_files),
                        model=model,
                        base_sha=base_sha,
                        existing_item_ids=existing_item_ids,
                        pr_identifier_service=pr_identifier_service,
                        review_session=review_session,
                    ),
                )
                result = outcome.review
            except LlmUnavailableError:
                logger.warning(
                    "Re-run attempt %d: LLM unavailable; %s",
                    attempt + 1,
                    self._inconclusive_disposition(),
                )
                return self._resolve_inconclusive(best)
            if outcome.has_items:
                logger.info(
                    "Re-run attempt %d produced %d items",
                    attempt + 1,
                    len(result.items),
                )
                return result
            if not outcome.is_clean_refutation:
                logger.info(
                    "Re-run attempt %d reached a genuine clean approval",
                    attempt + 1,
                )
                return result
            evidence.append(self._attempt_evidence(
                attempt=attempt + 1,
                reported=outcome.dropped_findings + len(result.items),
                dropped=outcome.dropped_findings,
                result=result,
            ))
            previous_result = result
            if len(result.summary or result.reason) > len(
                best.summary or best.reason
            ):
                best = result
        logger.warning(
            "All %d re-run attempts inconclusive; %s",
            self._max_tries,
            self._inconclusive_disposition(),
        )
        return self._resolve_inconclusive(best)

    @staticmethod
    def _attempt_evidence(
        attempt: int,
        reported: int,
        dropped: int,
        result: CodeReview,
    ) -> dict[str, Any]:
        """Record one re-run attempt's outcome for grounding the next prompt."""
        return {
            "attempt": attempt,
            "reported": reported,
            "dropped": dropped,
            "survived": len(result.items),
            "verdict": result.verdict.value,
            "explanation": (
                result.summary or result.reason
                or "no explanation provided"
            ),
        }

    def _inconclusive_disposition(self) -> str:
        """Return the terminal description for an inconclusive review."""
        return "refusing to publish a hollow review"

    def _resolve_inconclusive(self, best: CodeReview) -> CodeReview:
        """Refuse to publish an inconclusive review."""
        logger.error(
            "Review inconclusive after %d tries; no genuine verdict; "
            "refusing to publish a hollow review",
            self._max_tries,
        )
        raise ReviewVerdictError(
            "Review remained inconclusive after "
            f"{self._max_tries} attempts; no genuine verdict is available."
        )

    def _build_feedback_context(
        self,
        result: CodeReview,
        attempt_number: int,
        evidence: list[dict[str, Any]],
    ) -> str:
        """Build a re-run prompt grounded in prior attempts' results."""
        return self._feedback_renderer.render_content(
            round_number=attempt_number,
            escalation=self._escalation_for(attempt_number, evidence),
            previous_verdict=result.verdict.value,
            previous_explanation=(
                result.summary or result.reason or "no explanation provided"
            ),
            attempts=evidence,
        )

    def _escalation_for(
        self, attempt_number: int, evidence: list[dict[str, Any]]
    ) -> str:
        """Render the attempt-specific guidance for the re-run prompt."""
        if attempt_number == 1:
            return (
                "Re-examine the diff carefully and confirm any issue by "
                "reading the affected files before reporting it. Only "
                "report issues you can confirm against the source."
            )
        attempted = ", ".join(
            f"attempt {entry['attempt']} reported {entry['reported']} "
            f"finding(s) but none survived source verification"
            for entry in evidence
            if entry.get("attempt", 1) > 0
        )
        return (
            f"This is re-examination attempt {attempt_number}. Prior "
            f"{attempted}. Re-derive a genuine verdict from the actual "
            "source: approve only if nothing actionable remains, "
            "otherwise flag what you can confirm. Finding nothing again "
            "is a valid outcome — explain why the change is correct."
        )

    def _run_phases(
        self,
        plan: ReviewPlan,
        repo_path: Path | None = None,
        changed_files: list[str] | None = None,
        model: str = "",
        accumulated_items: list[ReviewItem] | None = None,
        initial_feedback: str = "",
        existing_item_ids: frozenset[str] = frozenset(),
        pr_identifier_service: str = "",
        review_session: str = "",
        base_sha: str = "",
        prior_items: list[ReviewItem] | None = None,
        context: ReviewExecutionContext | None = None,
    ) -> _PhaseRunOutcome:
        """Run phases with a shared context or legacy arguments."""
        if context is None and repo_path is None:
            raise ValueError("repo_path is required without a review context")
        execution_context = context or ReviewExecutionContext(
            repo_path=repo_path or Path(),
            changed_files=tuple(changed_files or []),
            model=model,
            base_sha=base_sha,
            existing_item_ids=existing_item_ids,
            pr_identifier_service=pr_identifier_service,
            review_session=review_session,
            prior_items=tuple(prior_items or []),
        )
        return self._run_phases_with_context(
            plan,
            execution_context,
            accumulated_items=accumulated_items,
            initial_feedback=initial_feedback,
        )

    def _run_phases_with_context(
        self,
        plan: ReviewPlan,
        context: ReviewExecutionContext,
        accumulated_items: list[ReviewItem] | None = None,
        initial_feedback: str = "",
    ) -> _PhaseRunOutcome:
        """Orchestrate all review phases, merging results."""
        repo_path = context.repo_path
        changed_files = list(context.changed_files)
        model = context.model
        existing_item_ids = context.existing_item_ids
        pr_identifier_service = context.pr_identifier_service
        review_session = context.review_session
        base_sha = context.base_sha
        prior_items = list(context.prior_items)
        all_items: list[ReviewItem] = []
        last_phase_result: PhaseResult | None = None
        phase_results: dict[str, PhaseResult] = {}
        previous_findings: str = ""
        phase_sequence = list(plan.phases)
        next_manager_brief = ""
        if self._manager is not None and phase_sequence:
            next_manager_brief = self._manager.brief(
                phase_sequence[0],
                "(Review start — no findings recorded yet.)",
                pr_identifier_service=pr_identifier_service,
                review_session=review_session,
            )

        for idx, phase in enumerate(phase_sequence):
            logger.info("Starting phase: %s", phase.phase_name)
            role_brief = phase.role_brief()
            manager_brief = getattr(plan, "manager_brief", "")
            assignment = manager_brief or next_manager_brief
            phase_prompt = self._phase_prompt_renderer.render_content(
                feedback=initial_feedback,
                assignment=assignment,
                role_brief=role_brief,
                methodology=plan.methodology,
                system_prompt=phase.system_prompt,
            )

            if _FINDINGS_MARKER in phase_prompt:
                phase_prompt = phase_prompt.replace(
                    _FINDINGS_MARKER,
                    previous_findings or "No findings from prior phases.",
                )

            # Combine existing IDs from command with IDs from items accumulated so far
            existing_ids = frozenset(
                item.id for item in all_items if item.id
            ) | existing_item_ids
            phase_result = self._run_phase_with_retry(
                phase_name=phase.phase_name,
                phase_prompt=phase_prompt,
                repo_path=repo_path,
                changed_files=changed_files,
                base_sha=base_sha,
                review_session=review_session,
                existing_item_ids=existing_ids,
            )
            phase_result = self._adjudicate_phase(
                phase=phase,
                phase_prompt=phase_prompt,
                assignment=assignment,
                pr_identifier_service=pr_identifier_service,
                review_session=review_session,
                base_sha=base_sha,
                phase_result=phase_result,
                repo_path=repo_path,
                changed_files=changed_files,
                existing_item_ids=existing_ids,
            )
            phase_results[phase.phase_id] = phase_result
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
            if (
                self._manager is not None
                and idx < len(phase_sequence) - 1
            ):
                next_manager_brief = self._manager.brief(
                    phase_sequence[idx + 1], previous_findings,
                    pr_identifier_service=pr_identifier_service,
                    review_session=review_session,
                )

        suggestion_phase_id = getattr(plan, "suggestions_phase_id", None)
        suggestions_source = (
            phase_results.get(suggestion_phase_id)
            if suggestion_phase_id
            else None
        ) or last_phase_result

        if not all_items:
            reason = ""
            summary = ""
            suggestions: list[ReviewItem] = []
            praise_list: list[ReviewItem] = []

            coerced = (
                ReviewVerdict.coerce(last_phase_result.llm_verdict)
                if last_phase_result is not None
                else None
            )

            if last_phase_result is not None:
                if last_phase_result.llm_reason:
                    reason = last_phase_result.llm_reason
                if last_phase_result.llm_summary:
                    summary = last_phase_result.llm_summary
                for s in suggestions_source.llm_suggestions:
                    normalized_path = ReviewItemFactory._normalize_file_path(
                        s.get("file", ""), repo_path, changed_files,
                    ) or ""
                    suggestions.append(ReviewItem(
                        severity=ItemSeverity.INFO,
                        category=IssueCategory.GENERAL,
                        file_path=normalized_path,
                        description=s.get("description", ""),
                        line=s.get("line", ""),
                        id=s.get("id", ""),
                        current_code=s.get("current_code", ""),
                        suggested_fix=s.get("suggested_fix", ""),
                    ))
                praise_entries: list[dict[str, str]] = []
                for pr in phase_results.values():
                    for p in pr.llm_praise:
                        if p not in praise_entries:
                            praise_entries.append(p)
                for p in praise_entries:
                    normalized_path = ReviewItemFactory._normalize_file_path(
                        p.get("file", ""), repo_path, changed_files,
                    ) or ""
                    praise_list.append(ReviewItem(
                        severity=ItemSeverity.INFO,
                        category=IssueCategory.GENERAL,
                        file_path=normalized_path,
                        description=p.get("description", ""),
                        line="",
                        id="",
                        current_code="",
                        suggested_fix="",
                    ))

            skipped = [
                skip_reason
                for phase_result in phase_results.values()
                for skip_reason in phase_result.skip_reasons
            ]
            model_reported_findings = bool(skipped)

            # The application automates PR interaction: it must never
            # publish a hollow COMMENTED outcome. Every zero-items review
            # resolves to a real verdict from the model's evidence — or
            # the pipeline failure raises instead of defaulting.
            if model_reported_findings:
                verdict = ReviewVerdict.CHANGES_REQUESTED
                dropped_list = "; ".join(skipped[:3])
                reason = (
                    f"The model reported {len(skipped)} finding(s) that "
                    "did not survive verification against the source code."
                )
                summary = (
                    f"Reviewed {len(plan.phases)} phases over model {model}; "
                    f"the model reported {len(skipped)} finding(s) that were "
                    "dropped during source verification and were not "
                    f"published. {dropped_list}"
                )
            elif coerced is not None and coerced is not ReviewVerdict.COMMENTED:
                # A real, non-blank model verdict with zero kept items is a
                # clean approval: nothing survived to flag.
                verdict = ReviewVerdict.APPROVED
                if not reason:
                    reason = "Review completed without action items."
                if not summary:
                    summary = reason
            else:
                raise ReviewVerdictError(
                    "No review phase produced a structured verdict and no "
                    "findings survived verification; refusing to publish a "
                    "default COMMENTED review."
                )

            return _PhaseRunOutcome(
                review=CodeReview(
                    verdict=verdict,
                    reason=reason,
                    summary=summary,
                    suggestions=suggestions,
                    praise=praise_list,
                    model_used=model,
                ),
                dropped_findings=len(skipped),
            )

        code_review = self._command_bus.dispatch(
            AggregateReviewFindingsCommand(
                items=all_items,
                phase_result=last_phase_result,
                suggestions_phase_result=suggestions_source,
                model_used=model,
                repo_path=repo_path,
                changed_files=changed_files,
            )
        )
        items_before_verification = len(code_review.items)
        if code_review.items or prior_items:
            verified_items = self._command_bus.dispatch(
                VerifyFindingsCommand(
                    items=code_review.items,
                    repo_path=repo_path,
                    changed_files=changed_files,
                    base_sha=base_sha,
                    review_session=review_session,
                    prior_items=prior_items or [],
                )
            )
            if (
                verified_items is not None
                and verified_items is not code_review.items
            ):
                code_review = self._rebuild_after_verification(
                    verified_items, model, previous=code_review,
                )
        if (
            code_review.verdict is ReviewVerdict.APPROVED
            and any(item.is_open_blocking for item in code_review.items)
        ):
            code_review = replace(
                code_review,
                verdict=ReviewVerdict.CHANGES_REQUESTED,
            )
        self._publish(FindingsAggregatedEvent(code_review=code_review))
        return _PhaseRunOutcome(
            review=code_review,
            dropped_findings=(
                items_before_verification - len(code_review.items)
            ),
        )

    def _rebuild_after_verification(
        self, verified_items: list[Any], model: str,
        previous: CodeReview | None = None,
    ) -> CodeReview:
        """Rebuild a CodeReview after verification dropped some items."""
        previous_items = len(previous.items) if previous is not None else 0

        review_items = [
            item for item in verified_items if isinstance(item, ReviewItem)
        ]
        verdict = SubReviewGuardrails().verdict_for(review_items)

        dropped = previous_items - len(review_items)
        if dropped and not review_items:
            reported_findings = (
                list(previous.items) if previous is not None else []
            )
            described = self._describe_dropped_findings(reported_findings)
            reason = (
                "The reported issues did not survive verification against "
                "the actual source: reading the affected files showed they "
                f"do not correspond to a real defect — {described}. No "
                "actionable change is required."
            )
            summary = (
                "The review examined the diff and cross-checked each "
                "reported concern against the source as written. "
                f"{described} These were refuted during source-code "
                "verification, so the change is assessed as correct with "
                "no actionable findings."
            )
        elif dropped and review_items:
            blocking = [item for item in review_items if item.is_blocking]
            target = blocking[0] if blocking else review_items[0]
            desc = target.description.strip()
            sev = str(target.severity).lower()
            file_path = target.file_path.strip()
            file_str = f" in {file_path}" if file_path else ""
            reason = f"Identified {sev} issue{file_str}: {desc}" if desc else "Findings verified against source code."
            cat_list = sorted({str(item.category) for item in review_items if item.category})
            cat_str = f" ({', '.join(cat_list)})" if cat_list else ""
            if blocking:
                summary = (
                    f"Verified {len(review_items)} finding(s){cat_str} with {len(blocking)} blocking issue(s) "
                    f"({dropped} dropped during verification)."
                )
            else:
                summary = (
                    f"Verified {len(review_items)} non-blocking finding(s){cat_str} "
                    f"({dropped} dropped during verification)."
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

    @staticmethod
    def _describe_dropped_findings(findings: list[ReviewItem]) -> str:
        """Describe which reported findings were refuted, for a real summary."""
        if not findings:
            return "no findings were substantiated"
        parts: list[str] = []
        for item in findings[:3]:
            location = f" in {item.file_path}" if item.file_path else ""
            description = item.description.strip()
            parts.append(f"\"{description}\"{location}")
        joined = "; ".join(parts)
        extra = f" (and {len(findings) - 3} more)" if len(findings) > 3 else ""
        return f"specifically, {joined}{extra}"

    def _run_phase_with_retry(
        self,
        phase_name: str,
        phase_prompt: str,
        repo_path: Path,
        changed_files: list[str],
        review_session: str,
        base_sha: str = "",
        existing_item_ids: frozenset[str] = frozenset(),
    ) -> PhaseResult:
        """Run a single phase with per-phase retry on exhaustion."""
        tool_service = self._tool_factory(
            repo_path, changed_files, base_sha
        )
        for retry in range(self._max_retries):
            if (
                self._max_conversations is not None
                and self._conversations_started >= self._max_conversations
            ):
                raise ReviewBudgetExhaustedError(
                    f"Review conversation budget of {self._max_conversations}"
                    " exhausted; stopping before starting another phase"
                    " conversation"
                )
            self._conversations_started += 1
            try:
                return self._command_bus.dispatch(
                    RunAgentConversationCommand(
                        system_prompt=phase_prompt,
                        repo_path=repo_path,
                        changed_files=changed_files,
                        tool_execution=tool_service,
                        phase_name=phase_name,
                        existing_item_ids=existing_item_ids,
                        review_session=review_session,
                    )
                )
            except (MaxTurnsExceededError, AdvisorBlockedError) as exc:
                if retry == self._max_retries - 1:
                    raise
                logger.warning(
                    "Phase %s did not converge (%s); restarting "
                    "(attempt %d/%d)",
                    phase_name,
                    type(exc).__name__,
                    retry + 1,
                    self._max_retries,
                )
                tool_service = self._tool_factory(
                    repo_path, changed_files, base_sha
                )
        raise RuntimeError("Unreachable: _max_retries must be >= 1")

    def _adjudicate_phase(
        self,
        phase: ReviewPhase,
        phase_prompt: str,
        assignment: str,
        phase_result: PhaseResult,
        repo_path: Path,
        changed_files: list[str],
        existing_item_ids: frozenset[str],
        pr_identifier_service: str = "",
        review_session: str = "",
        base_sha: str = "",
    ) -> PhaseResult:
        """Grade the finished phase with the advisor and re-run it on a blocking grade.

        The advisor watches the peer after every phase. When the grade
        blocks (F — don't do this!), the phase's output is discarded and
        the phase is restarted with the advisor's improved version of the
        original prompt, exactly once. Any non-blocking grade (S/B/D), or
        an absent advisor, accepts the output unchanged.
        """
        if self._advisor is None:
            return phase_result
        directive: AdvisorDirective = self._advisor.assess(
            phase, assignment, phase_result, pr_identifier_service=pr_identifier_service,
            review_session=review_session,
        )
        if not directive.blocks_output:
            return phase_result
        evidence = self._phase_evidence(
            phase_prompt, assignment, phase_result,
        )
        correction_text = self._identifier_filter.strip_unobserved(
            directive.improved_prompt or directive.feedback, evidence,
        )
        improved_task = ""
        if self._manager is not None:
            improved_task = self._manager.brief(
                phase,
                directive.feedback or "phase drifted off its task",
                pr_identifier_service=pr_identifier_service,
                review_session=review_session,
            )
        corrected_prompt = self._correction_renderer.render_content(
            phase_prompt=phase_prompt,
            correction=correction_text,
            manager_replan=improved_task,
        )
        logger.warning(
            "Advisor blocked phase %s (F); discarding output and "
            "restarting with the manager's improved prompt",
            phase.phase_name,
        )
        return self._run_phase_with_retry(
            phase_name=phase.phase_name,
            phase_prompt=corrected_prompt,
            repo_path=repo_path,
            changed_files=changed_files,
            base_sha=base_sha,
            review_session=review_session,
            existing_item_ids=existing_item_ids,
        )

    @staticmethod
    def _phase_evidence(
        phase_prompt: str,
        assignment: str,
        phase_result: PhaseResult,
    ) -> str:
        """Return the observed text a correction may legitimately cite."""
        item_text = "\n".join(
            f"{getattr(item, 'description', '')} "
            f"{getattr(item, 'file_path', '')}"
            for item in phase_result.items
        )
        return "\n".join([
            phase_prompt,
            assignment or "",
            phase_result.llm_reason or "",
            phase_result.llm_summary or "",
            item_text,
        ])

    def _is_max_turns_exceeded(self, exc: LlmUnavailableError) -> bool:
        return isinstance(exc, MaxTurnsExceededError)

    def _extract_repo_and_pr(self, repo_path: Path) -> tuple[str, str]:
        """Extract (repo_name, pr_id) from repo_path."""
        identifier = PRIdentifierService.derive(repo_path)
        if "#" not in identifier:
            return identifier, ""
        repo_name, pr_number = identifier.rsplit("#", 1)
        return repo_name, pr_number

    def _publish(self, event: Any) -> None:
        """Publish an event to the bus."""
        self._command_bus.dispatch(event)

