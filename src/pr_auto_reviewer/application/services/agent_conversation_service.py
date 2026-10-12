"""AgentConversationService — run a multi-turn agentic conversation with tool access."""

from __future__ import annotations

import json
import logging
import re
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

from pr_auto_reviewer.application.ports.inbound.run_agent_conversation_port import (
    RunAgentConversationPort,
)
from pr_auto_reviewer.application.ports.outbound.agent_chat_port import (
    AgentChatPort,
)
from pr_auto_reviewer.application.ports.outbound.command_bus_port import (
    CommandBusPort,
)
from pr_auto_reviewer.application.ports.outbound.conversation_logger_port import (
    TranscriptMetadata,
)
from pr_auto_reviewer.application.services.pr_identifier_service import (
    PRIdentifierService,
)
from pr_auto_reviewer.domain.exceptions.advisor_blocked_error import (
    AdvisorBlockedError,
)
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.domain.exceptions.max_turns_exceeded_error import (
    MaxTurnsExceededError,
)
from pr_auto_reviewer.domain.exceptions.review_budget_exhausted_error import (
    ReviewBudgetExhaustedError,
)
from pr_auto_reviewer.domain.messages.commands.parse_review_turn_command import (
    ParseReviewTurnCommand,
)
from pr_auto_reviewer.domain.messages.commands.run_agent_conversation_command import (
    RunAgentConversationCommand,
)
from pr_auto_reviewer.domain.messages.events.conversation_completed_event import (
    ConversationCompletedEvent,
)
from pr_auto_reviewer.domain.messages.events.review_turn_parsed_event import (
    ReviewTurnParsedEvent,
)
from pr_auto_reviewer.domain.services.review_item_factory import (
    ReviewItemFactory,
)
from pr_auto_reviewer.domain.services.suggestion_scope_policy import (
    SuggestionScopePolicy,
)
from pr_auto_reviewer.domain.value_objects.conversation_decision import (
    ConversationDecision,
)
from pr_auto_reviewer.domain.value_objects.conversation_guardrails import (
    ConversationGuardrails,
)
from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.domain.value_objects.phase_result import PhaseResult
from pr_auto_reviewer.domain.value_objects.sub_agent_grade import SubAgentGrade
from pr_auto_reviewer.domain.value_objects.turn_kind import TurnKind
from pr_auto_reviewer.domain.value_objects.turn_parse_result import TurnParseResult
from pr_auto_reviewer.infrastructure.templates.conversation_renderers import (
    AdvisorBlockMessageRenderer,
    AdvisorFeedbackMessageRenderer,
    EmptyResponseMessageRenderer,
    ExploreBeforeVerdictMessageRenderer,
    ForceVerdictMessageRenderer,
    InitialUserMessageRenderer,
    RepeatedToolCallMessageRenderer,
    SuggestionsPraiseMessageRenderer,
    UnparseableResponseMessageRenderer,
)

logger = logging.getLogger(__name__)
_MAX_REPEATED_TOOL_CALLS = 3



class AgentConversationService(RunAgentConversationPort):
    """Run a multi-turn agentic conversation with tool access.

    Orchestrates the loop: send messages → parse response → execute
    tools → append results → repeat until verdict or exhaustion. Every
    reprompt and termination decision is delegated to
    ``ConversationGuardrails``.
    """

    def __init__(
        self,
        chat_port: AgentChatPort,
        command_bus: CommandBusPort,
        conversation_logger: Any = None,
        *,
        max_turns: int,
        max_empty_responses: int = 3,
        max_unparseable_responses: int = 3,
        turn_observer: Any = None,
        max_advisor_blocks: int = 2,
    ) -> None:
        self._chat_port = chat_port
        self._command_bus = command_bus
        self._conversation_logger = conversation_logger
        self._turn_observer = turn_observer
        self._max_advisor_blocks = max_advisor_blocks
        self._guardrails = ConversationGuardrails(
            max_turns=max_turns,
            max_empty_responses=max_empty_responses,
            max_unparseable_responses=max_unparseable_responses,
        )
        self._initial_message = InitialUserMessageRenderer()
        self._empty_message = EmptyResponseMessageRenderer()
        self._unparseable_message = UnparseableResponseMessageRenderer()
        self._advisor_block_message = AdvisorBlockMessageRenderer()
        self._advisor_feedback_message = AdvisorFeedbackMessageRenderer()
        self._repeated_tool_message = RepeatedToolCallMessageRenderer()
        self._force_verdict_message = ForceVerdictMessageRenderer()
        self._explore_message = ExploreBeforeVerdictMessageRenderer()
        self._suggestions_praise_message = SuggestionsPraiseMessageRenderer()

    def execute(
        self, command: RunAgentConversationCommand
    ) -> PhaseResult:
        """Run a single-phase multi-turn conversation."""
        return self._run(
            system_prompt=command.system_prompt,
            repo_path=command.repo_path,
            changed_files=command.changed_files,
            coverage_files=command.coverage_files,
            tool_execution=command.tool_execution,
            phase_name=command.phase_name,
            review_session=command.review_session,
            existing_item_ids=command.existing_item_ids,
        )

    def _derive_pr_identifier(self, repo_path: Path | None) -> str:
        return PRIdentifierService.derive(repo_path)

    def _guardrails_for_files(
        self, repo_path: Path, changed_files: list[str],
    ) -> ConversationGuardrails:
        """Scale exploration budgets to the readable changed-file set."""
        readable_files = self._readable_changed_files(repo_path, changed_files)
        required_reads = len(readable_files)
        return replace(
            self._guardrails,
            max_tool_calls=max(
                self._guardrails.max_tool_calls, required_reads + 3,
            ),
            max_turns=max(self._guardrails.max_turns, required_reads + 5),
        )

    @staticmethod
    def _readable_changed_files(
        repo_path: Path, changed_files: list[str],
    ) -> tuple[str, ...]:
        """Return changed files that can be inspected in the checked-out tree."""
        root = repo_path.resolve()
        readable: list[str] = []
        for file_path in changed_files:
            candidate = (root / file_path).resolve()
            if candidate.is_relative_to(root) and candidate.is_file():
                readable.append(file_path)
        return tuple(readable)

    @staticmethod
    def _normalize_read_file_path(
        raw_path: str, repo_path: Path, changed_files: tuple[str, ...],
    ) -> str | None:
        """Map a successful tool path to its changed-file spelling."""
        candidate = Path(raw_path)
        if candidate.is_absolute():
            try:
                candidate = candidate.resolve().relative_to(repo_path.resolve())
            except ValueError:
                return None
        normalized = candidate.as_posix()
        for changed_file in changed_files:
            if Path(changed_file).as_posix() == normalized:
                return changed_file
        return None

    def _record_read_file(
        self,
        result: Any,
        repo_path: Path,
        changed_files: tuple[str, ...],
        read_file_paths: set[str],
    ) -> None:
        """Record a changed file only after a successful read."""
        if getattr(result, "status", "") != "ok":
            return
        data = getattr(result, "data", None)
        raw_path = data.get("path") if isinstance(data, dict) else None
        if isinstance(raw_path, str):
            normalized = self._normalize_read_file_path(
                raw_path, repo_path, changed_files,
            )
            if normalized is not None:
                read_file_paths.add(normalized)

    @staticmethod
    def _coverage_complete(
        guardrails: ConversationGuardrails,
        readable_changed_files: tuple[str, ...],
        read_file_paths: set[str],
    ) -> bool:
        """Return whether the phase has explored and covered every target file."""
        return (
            guardrails.tool_calls > 0
            and set(readable_changed_files).issubset(read_file_paths)
        )

    @staticmethod
    def _coverage_demand(missing_files: list[str]) -> str:
        """Describe the changed files still required before a verdict."""
        if not missing_files:
            return ""
        files = "\n".join(f"- {file_path}" for file_path in missing_files)
        return (
            "\nThe following changed files are still unread. Use read_file "
            "on each before concluding:\n" + files
        )

    def _find_mentioned_file(
        self, text: str, changed_files: list[str]
    ) -> str:
        """Return the changed file whose name appears in *text*; else empty."""
        if not text or not changed_files:
            return ""
        for candidate in sorted(changed_files, key=len, reverse=True):
            basename = candidate.rsplit("/", 1)[-1]
            stem = basename.rsplit(".", 1)[0]
            if self._contains_file_name(text, basename) or (
                stem and self._contains_file_name(text, stem)
            ):
                return candidate
        return ""

    @staticmethod
    def _contains_file_name(text: str, name: str) -> bool:
        """Return whether a file name appears as a distinct text token."""
        pattern = rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])"
        return re.search(pattern, text) is not None

    def _ground_cited_paths(
        self,
        entries: list[dict[str, Any]],
        kind: str,
        repo_path: Path,
        changed_files: list[str],
    ) -> list[dict[str, Any]]:
        """Validate cited ``file`` paths against the repository."""
        grounded: list[dict[str, Any]] = []
        for entry in entries:
            cited = str(entry.get("file", "")).strip()
            if not cited:
                grounded.append(entry)
                continue
            if kind == "suggestion":
                grounded_entry = self._ground_suggestion_citation(
                    entry, cited, repo_path, changed_files,
                )
                if grounded_entry is not None:
                    grounded.append(grounded_entry)
                continue
            grounded_entry = self._ground_non_suggestion_citation(
                entry, cited, kind, repo_path, changed_files,
            )
            if grounded_entry is not None:
                grounded.append(grounded_entry)
        return grounded

    def _ground_suggestion_citation(
        self,
        entry: dict[str, Any],
        cited: str,
        repo_path: Path,
        changed_files: list[str],
    ) -> dict[str, Any] | None:
        """Return a suggestion with a safe, evidenced path or ``None``."""
        normalized = None
        if not self._is_external_absolute_path(cited, repo_path):
            normalized = ReviewItemFactory._normalize_file_path(
                cited, repo_path, changed_files,
            )
        if (
            normalized
            and normalized not in changed_files
            and not self._resolves_inside_repo(normalized, repo_path)
        ):
            normalized = None
        description = str(entry.get("description", ""))
        if not SuggestionScopePolicy.keep(
            cited, description, changed_files, normalized,
        ):
            logger.info(
                "Dropping suggestion citation without scope evidence: %s",
                cited,
            )
            return None
        entry["file"] = normalized or ""
        return entry

    def _ground_non_suggestion_citation(
        self,
        entry: dict[str, Any],
        cited: str,
        kind: str,
        repo_path: Path,
        changed_files: list[str],
    ) -> dict[str, Any] | None:
        """Return a grounded non-suggestion entry or ``None``."""
        exists = (
            cited in changed_files
            or self._resolves_inside_repo(cited, repo_path)
        )
        if exists:
            return entry
        logger.info(
            "Dropping %s citation of nonexistent path: %s",
            kind, cited,
        )
        if kind == "praise":
            return None
        entry["file"] = ""
        return entry

    @staticmethod
    def _is_external_absolute_path(cited: str, repo_path: Path) -> bool:
        """Return whether an absolute citation resolves outside the clone."""
        cited_path = Path(cited)
        return (
            cited_path.is_absolute()
            and not cited_path.resolve().is_relative_to(repo_path.resolve())
        )

    def _resolves_inside_repo(self, cited: str, repo_path: Path) -> bool:
        """Return whether *cited* resolves to an existing repo-internal path."""
        resolved = (repo_path / cited).resolve()
        return (
            resolved.is_relative_to(repo_path.resolve())
            and resolved.exists()
        )

    def _log_conversation_debug(
        self,
        phase_name: str,
        messages: list[ConversationMessage],
        turns: int,
        phase_result: PhaseResult | None,
        repo_path: Path | None = None,
    ) -> None:
        """Emit the full conversation when the CLI runs in debug mode."""
        if not logger.isEnabledFor(logging.DEBUG):
            return
        verdict = phase_result.llm_verdict if phase_result else "exhausted"
        item_count = len(phase_result.items) if phase_result else 0
        logger.debug(
            "=== Conversation: %s (turns=%d, verdict=%s, items=%d) ===",
            phase_name, turns, verdict, item_count,
        )
        for message in messages:
            role = getattr(message, "role", "unknown")
            content = getattr(message, "content", "")
            logger.debug(
                "--- %s ---\n%s", role, str(content)
            )
    def _run(
        self,
        system_prompt: str,
        repo_path: Path,
        changed_files: list[str],
        coverage_files: tuple[str, ...] | None,
        tool_execution: Any,
        review_session: str,
        phase_name: str = "",
        existing_item_ids: frozenset[str] = frozenset(),
    ) -> PhaseResult:
        """Run a single-phase multi-turn conversation.

        Raises:
            LlmUnavailableError: If the conversation exhausts all turns
                without reaching a verdict.
        """
        file_listing = (
            "\n  - ".join(changed_files) if changed_files else "(none)"
        )
        messages: list[ConversationMessage] = [
            ConversationMessage(role="system", content=system_prompt),
            self._initial_message.render(
                file_listing=file_listing, repo_path=repo_path
            ),
        ]

        coverage_targets = (
            changed_files if coverage_files is None else list(coverage_files)
        )
        guardrails = self._guardrails_for_files(repo_path, coverage_targets)
        readable_changed_files = self._readable_changed_files(
            repo_path, changed_files,
        )
        readable_coverage_files = self._readable_changed_files(
            repo_path, coverage_targets,
        )
        seen_tool_calls: set[tuple[str, str]] = set()
        read_file_paths: set[str] = set()
        accumulated_praise: list[dict[str, Any]] = []
        accumulated_suggestions: list[dict[str, Any]] = []
        self._consecutive_blocks = 0
        verdict_nudged = False
        read_file_count = 0
        run_snippet_count = 0
        repeated_tool_call_streak = 0

        while guardrails.has_turns_remaining():
            logger.debug(
                "Turn %d/%d", guardrails.turn + 1, guardrails.max_turns
            )
            content = self._chat_port.send(messages)
            guardrails = guardrails.advance_turn()
            if not content:
                decision, guardrails = guardrails.record_empty_response()
                if decision is ConversationDecision.EXCEEDED_EMPTY:
                    raise LlmUnavailableError(
                        f"LLM returned empty response "
                        f"{guardrails.consecutive_empty} consecutive times "
                        f"at turn {guardrails.turn}"
                    )
                logger.debug(
                    "Empty response at turn %d; reprompting", guardrails.turn
                )
                messages.append(self._empty_message.render())
                continue

            guardrails = guardrails.mark_consecutive_success()

            parsed = self._command_bus.dispatch(
                ParseReviewTurnCommand(content=content)
            )
            self._publish(ReviewTurnParsedEvent(
                turn_number=guardrails.turn, result=parsed
            ))
            if parsed.metadata:
                if parsed.metadata.get("praise"):
                    accumulated_praise = list(parsed.metadata["praise"])
                if parsed.metadata.get("suggestions"):
                    accumulated_suggestions = list(parsed.metadata["suggestions"])
            if self._turn_observer is not None and parsed.kind is not TurnKind.VERDICT:
                directive = self._turn_observer.observe(
                    content, phase_name, review_session,
                    pr_identifier_service=self._derive_pr_identifier(repo_path),
                    changed_files=changed_files,
                )
                if directive.blocks_output:
                    self._consecutive_blocks += 1
                    messages.append(
                        self._advisor_block_message.render(
                            feedback=directive.feedback
                        )
                    )
                    if self._consecutive_blocks >= self._max_advisor_blocks:
                        self._log_conversation(
                            phase_name, messages, guardrails.turn, None,
                            repo_path=repo_path, review_session=review_session,
                        )
                        raise AdvisorBlockedError(
                            f"Advisor blocked phase {phase_name} after "
                            f"{self._consecutive_blocks} blocking grades"
                        )
                else:
                    self._consecutive_blocks = 0
                    if directive.feedback and directive.grade is (
                        SubAgentGrade.WHATEVER
                    ):
                        messages.append(
                            self._advisor_feedback_message.render(
                                feedback=directive.feedback
                            )
                        )

            if parsed.kind is TurnKind.UNPARSEABLE:
                decision, guardrails = guardrails.record_unparseable_response()
                if decision is ConversationDecision.EXCEEDED_UNPARSEABLE:
                    raise LlmUnavailableError(
                        f"LLM returned unparseable response "
                        f"{guardrails.consecutive_unparseable} consecutive "
                        f"times at turn {guardrails.turn}"
                    )
                logger.debug(
                    "Unparseable response at turn %d; reprompting",
                    guardrails.turn,
                )
                messages.append(self._unparseable_message.render())
                continue

            messages.append(ConversationMessage(
                role="assistant", content=content
            ))

            if parsed.kind is TurnKind.TOOL_CALL and parsed.tool_call is not None:
                tool_call = parsed.tool_call
                logger.debug(
                    "Tool call — action=%s args=%s",
                    tool_call.tool_name,
                    str(tool_call.arguments)[:200],
                )
                call_key = (
                    tool_call.tool_name,
                    json.dumps(
                        tool_call.arguments, sort_keys=True, default=str
                    ),
                )
                if call_key in seen_tool_calls:
                    repeated_tool_call_streak += 1
                    logger.debug(
                        "Tool call repeated (%s); refusing and reprompting",
                        tool_call.tool_name,
                    )
                    if repeated_tool_call_streak >= _MAX_REPEATED_TOOL_CALLS:
                        logger.warning(
                            "Aborting conversation after %d repeated tool calls",
                            repeated_tool_call_streak,
                        )
                        raise ReviewBudgetExhaustedError(
                            "Conversation made no progress after repeated tool calls"
                        )
                    messages.append(self._repeated_tool_message.render())
                    continue
                repeated_tool_call_streak = 0
                seen_tool_calls.add(call_key)
                result = tool_execution.execute_tool(tool_call)
                guardrails = guardrails.record_tool_call()
                if tool_call.tool_name == "read_file":
                    read_file_count += 1
                    self._record_read_file(
                        result,
                        repo_path,
                        readable_changed_files,
                        read_file_paths,
                    )
                elif tool_call.tool_name == "run_snippet":
                    run_snippet_count += 1
                result_json = json.dumps({
                    "status": result.status,
                    "data": result.data,
                    "error": result.error,
                })
                logger.debug(
                    "Tool result (%d chars): %s",
                    len(result_json),
                    result_json[:300],
                )
                messages.append(ConversationMessage(
                    role="user",
                    content=result_json,
                    tool_result=result,
                ))
                if guardrails.should_force_verdict() and not verdict_nudged:
                    verdict_nudged = True
                    logger.debug(
                        "Tool budget reached (%d); nudging verdict",
                        guardrails.tool_calls,
                    )
                    messages.append(self._force_verdict_message.render())
                continue

            if parsed.kind is TurnKind.VERDICT:
                coverage_complete = self._coverage_complete(
                    guardrails,
                    readable_coverage_files,
                    read_file_paths,
                )
                decision, guardrails = guardrails.judge_verdict(
                    exploration_complete=coverage_complete,
                )
                if decision is ConversationDecision.ACCEPT_VERDICT:
                    logger.debug("Got verdict at turn %d", guardrails.turn)
                    if guardrails.has_turns_remaining():
                        messages.append(self._suggestions_praise_message.render())
                        guardrails = guardrails.advance_turn()
                        try:
                            sp_content = self._chat_port.send(messages)
                        except (StopIteration, Exception) as e:
                            logger.debug("Suggestions/praise turn skipped: %s", e)
                            sp_content = None
                        if sp_content:
                            messages.append(ConversationMessage(
                                role="assistant", content=sp_content
                            ))
                            sp_parsed = self._command_bus.dispatch(
                                ParseReviewTurnCommand(content=sp_content)
                            )
                            if sp_parsed is not None and getattr(sp_parsed, "metadata", None):
                                new_praise = sp_parsed.metadata.get("praise") or []
                                for p in new_praise:
                                    if p not in accumulated_praise:
                                        accumulated_praise.append(p)
                                new_suggestions = sp_parsed.metadata.get("suggestions") or []
                                for s in new_suggestions:
                                    if s not in accumulated_suggestions:
                                        accumulated_suggestions.append(s)
                    phase_result = self._build_phase_result(
                        parsed, repo_path, changed_files,
                        turn_count=guardrails.turn,
                        read_file_calls=read_file_count,
                        read_file_paths=tuple(sorted(read_file_paths)),
                        run_snippet_calls=run_snippet_count,
                        unread_changed_files=tuple(
                            sorted(
                                set(readable_changed_files) - read_file_paths
                            )
                        ),
                        existing_ids=existing_item_ids,
                        accumulated_praise=accumulated_praise,
                        accumulated_suggestions=accumulated_suggestions,
                    )
                    self._log_conversation(
                        phase_name, messages, guardrails.turn, phase_result,
                        repo_path=repo_path, review_session=review_session,
                    )
                    self._publish(ConversationCompletedEvent(
                        phase_result=phase_result
                    ))
                    return phase_result
                if (
                    decision
                    == ConversationDecision.REFUSED_EXPLORATION
                ):
                    logger.warning(
                        "Model refused exploration after %d "
                        "demand(s); aborting phase",
                        guardrails.demands_issued,
                    )
                    raise MaxTurnsExceededError(
                        "Model refused exploration after "
                        f"{guardrails.demands_issued} demand(s)"
                    )
                missing_files = sorted(
                    set(readable_coverage_files) - read_file_paths
                )
                logger.debug(
                    "Verdict at turn %d without complete changed-file "
                    "coverage; demanding exploration",
                    guardrails.turn,
                )
                demand = self._explore_message.render()
                messages.append(
                    ConversationMessage(
                        role="user",
                        content=demand.content + self._coverage_demand(missing_files),
                    )
                )
                continue

        self._log_conversation(
            phase_name, messages, guardrails.turn, None,
            repo_path=repo_path, review_session=review_session,
        )
        fd, dump_path = tempfile.mkstemp(
            prefix="pr-review-exhausted-",
            suffix=".json",
        )
        with open(fd, "w") as f:
            json.dump(
                [{"role": m.role, "content": m.content} for m in messages],
                f,
                indent=2,
                default=str,
            )
        raise MaxTurnsExceededError(
            f"Phase exceeded max turns ({guardrails.max_turns}) "
            f"without a verdict. Full conversation dumped to {dump_path}"
        )

    def _build_phase_result(
        self, parsed: TurnParseResult, repo_path: Path, changed_files: list[str],
        turn_count: int = 0, read_file_calls: int = 0,
        read_file_paths: tuple[str, ...] = (),
        run_snippet_calls: int = 0,
        unread_changed_files: tuple[str, ...] = (),
        existing_ids: frozenset[str] = frozenset(),
        accumulated_praise: list[dict[str, Any]] | None = None,
        accumulated_suggestions: list[dict[str, Any]] | None = None,
    ) -> PhaseResult:
        """Build a ``PhaseResult`` from parsed turn data, validating against disk."""
        raw_items = parsed.raw_items or []
        metadata = parsed.metadata or {}

        review_items, skip_reasons = ReviewItemFactory().create(
            raw_items, repo_path, changed_files, existing_ids=existing_ids
        )
        raw_suggestions = (
            metadata.get("suggestions")
            or accumulated_suggestions
            or []
        )
        suggestions = list(raw_suggestions)
        for s in suggestions:
            if not str(s.get("file", "")).strip():
                s["file"] = self._find_mentioned_file(
                    str(s.get("description", "")), changed_files
                )
        suggestions = self._ground_cited_paths(
            suggestions, "suggestion", repo_path, changed_files,
        )
        raw_praise = (
            metadata.get("praise")
            or accumulated_praise
            or []
        )
        praise = self._ground_cited_paths(
            list(raw_praise), "praise",
            repo_path, changed_files,
        )
        return PhaseResult(
            items=review_items,
            llm_verdict=metadata.get("verdict") or None,
            llm_reason=metadata.get("reason", ""),
            llm_summary=metadata.get("summary", ""),
            llm_suggestions=suggestions,
            llm_praise=praise,
            turn_count=turn_count,
            read_file_calls=read_file_calls,
            read_file_paths=read_file_paths,
            run_snippet_calls=run_snippet_calls,
            unread_changed_files=unread_changed_files,
            skip_reasons=skip_reasons,
        )
    def _publish(self, event: Any) -> None:
        """Publish an event to the bus."""
        self._command_bus.dispatch(event)

    def _log_conversation(
        self,
        phase_name: str,
        messages: list[ConversationMessage],
        turns: int,
        phase_result: PhaseResult | None,
        repo_path: Path | None = None,
        review_session: str = "",
    ) -> None:
        self._log_conversation_debug(
            phase_name, messages, turns, phase_result, repo_path,
        )
        if self._conversation_logger is None:
            return

        pr_identifier_service = self._derive_pr_identifier(repo_path)
        skipped = (
            len(getattr(phase_result, "skip_reasons", []))
            if phase_result else 0
        )

        metadata: dict[str, Any] = {
            "model": "code-review:latest",
            "turns": turns,
            "verdict": (
                phase_result.llm_verdict if phase_result else "exhausted"
            ),
            "item_count": (
                len(getattr(phase_result, "items", []) or []) + skipped
                if phase_result else 0
            ),
            "skipped": skipped,
            TranscriptMetadata.READ_FILE_PATHS: (
                list(phase_result.read_file_paths)
                if phase_result else []
            ),
            TranscriptMetadata.UNREAD_CHANGED_FILES: (
                list(phase_result.unread_changed_files)
                if phase_result else []
            ),
        }

        try:
            self._conversation_logger.log_conversation(
                phase_name=phase_name or "unknown",
                pr_identifier_service=pr_identifier_service,
                messages=messages,
                metadata=metadata,
                review_session=review_session,
            )
        except Exception:
            logger.warning(
                "Failed to log conversation for phase %s", phase_name,
                exc_info=True,
            )
