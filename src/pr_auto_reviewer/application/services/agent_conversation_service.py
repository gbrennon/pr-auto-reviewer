"""AgentConversationService — run a multi-turn agentic conversation with tool access."""

from __future__ import annotations

import json
import logging
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

from pr_auto_reviewer.application.ports.inbound.run_agent_conversation_use_case import (
    RunAgentConversationUseCase,
)
from pr_auto_reviewer.application.ports.outbound.agent_chat_port import (
    AgentChatPort,
)
from pr_auto_reviewer.application.ports.outbound.command_bus_port import (
    CommandBusPort,
)
from pr_auto_reviewer.domain.agent.conversation_decision import (
    ConversationDecision,
)
from pr_auto_reviewer.domain.agent.conversation_guardrails import (
    ConversationGuardrails,
)
from pr_auto_reviewer.domain.agent.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.domain.agent.phase_result import PhaseResult
from pr_auto_reviewer.domain.agent.turn_parse_result import TurnParseResult
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
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

logger = logging.getLogger(__name__)



class AgentConversationService(RunAgentConversationUseCase):
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
        max_turns: int = 10,
        max_empty_responses: int = 3,
        max_unparseable_responses: int = 3,
    ) -> None:
        self._chat_port = chat_port
        self._command_bus = command_bus
        self._conversation_logger = conversation_logger
        self._guardrails = ConversationGuardrails(
            max_turns=max_turns,
            max_empty_responses=max_empty_responses,
            max_unparseable_responses=max_unparseable_responses,
        )

    def execute(
        self, command: RunAgentConversationCommand
    ) -> PhaseResult:
        """Run a single-phase multi-turn conversation."""
        return self._run(
            system_prompt=command.system_prompt,
            repo_path=command.repo_path,
            changed_files=command.changed_files,
            tool_execution=command.tool_execution,
            phase_name=command.phase_name,
            existing_item_ids=command.existing_item_ids,
        )

    def _derive_pr_identifier(self, repo_path: Path | None) -> str:
        if repo_path is None:
            return "unknown"
        path_str = str(repo_path)
        import re
        match = re.search(r"/repos/([^/]+)_([^/]+)_(\d+)$", path_str)
        if match:
            return f"{match.group(1)}/{match.group(2)}#{match.group(3)}"
        return path_str.rsplit("/", 1)[-1]


    def _find_mentioned_file(
        self, text: str, changed_files: list[str]
    ) -> str:
        """Return the changed file whose name appears in *text*; else empty."""
        if not text or not changed_files:
            return ""
        for candidate in sorted(changed_files, key=len, reverse=True):
            basename = candidate.rsplit("/", 1)[-1]
            stem = basename.rsplit(".", 1)[0]
            if basename in text or (stem and stem in text):
                return candidate
        return ""

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
        tool_execution: Any,
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
            ConversationMessage(
                role="user",
                content=(
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
            ),
        ]

        guardrails = replace(self._guardrails)
        while guardrails.has_turns_remaining():
            logger.debug(
                "Turn %d/%d", guardrails.turn + 1, self._guardrails.max_turns
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
                messages.append(ConversationMessage(
                    role="user",
                    content=(
                        "Your previous response was empty. Please continue "
                        "your analysis or provide your review findings as "
                        'a JSON object with "verdict", "reason", '
                        '"suggestions", "praise", and "items" keys.'
                    ),
                ))
                continue

            guardrails = guardrails.mark_consecutive_success()

            parsed = self._command_bus.dispatch(
                ParseReviewTurnCommand(content=content)
            )
            self._publish(ReviewTurnParsedEvent(
                turn_number=guardrails.turn, result=parsed
            ))

            if parsed.kind == "unparseable":
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
                messages.append(ConversationMessage(
                    role="user",
                    content=(
                        "Your previous response was not valid JSON. Please "
                        "respond with a JSON object containing either "
                        "'action' and 'args' for tool calls, or 'verdict', "
                        "'reason', 'suggestions', 'praise', and 'items' "
                        "for your final review findings."
                    ),
                ))
                continue

            messages.append(ConversationMessage(
                role="assistant", content=content
            ))

            if parsed.kind == "tool_call" and parsed.tool_call is not None:
                tool_call = parsed.tool_call
                logger.debug(
                    "Tool call — action=%s args=%s",
                    tool_call.tool_name,
                    str(tool_call.arguments)[:200],
                )
                result = tool_execution.execute_tool(tool_call)
                guardrails = guardrails.record_tool_call()
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
                ))
                continue

            if parsed.kind == "verdict":
                decision, guardrails = guardrails.judge_verdict()
                if decision is ConversationDecision.ACCEPT_VERDICT:
                    logger.debug("Got verdict at turn %d", guardrails.turn)
                    phase_result = self._build_phase_result(
                        parsed, repo_path, changed_files, existing_ids=existing_item_ids
                    )
                    self._log_conversation(
                        phase_name, messages, guardrails.turn, phase_result,
                        repo_path=repo_path,
                    )
                    self._publish(ConversationCompletedEvent(
                        phase_result=phase_result
                    ))
                    return phase_result
                logger.debug(
                    "Verdict at turn %d with no tool exploration; "
                    "demanding exploration",
                    guardrails.turn,
                )
                messages.append(ConversationMessage(
                    role="user",
                    content=(
                        "You reached a verdict without inspecting the "
                        "repository. Before concluding, you MUST use the "
                        "exploration tools (read_file, search_codebase, "
                        "list_directory, run_git) to inspect the changed "
                        "files. Do that now, then provide your final JSON "
                        "verdict."
                    ),
                ))
                continue
        self._log_conversation(
            phase_name, messages, self._guardrails.max_turns, None,
            repo_path=repo_path,
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
        raise LlmUnavailableError(
            f"Phase exceeded max turns ({self._guardrails.max_turns}) "
            f"without a verdict. Full conversation dumped to {dump_path}"
        )

    def _build_phase_result(
        self, parsed: TurnParseResult, repo_path: Path, changed_files: list[str], existing_ids: frozenset[str] = frozenset()
    ) -> PhaseResult:
        """Build a ``PhaseResult`` from parsed turn data, validating against disk."""
        raw_items = parsed.raw_items or []
        metadata = parsed.metadata or {}

        review_items, skip_reasons = ReviewItemFactory().create(
            raw_items, repo_path, changed_files, existing_ids=existing_ids
        )
        suggestions = list(metadata.get("suggestions", []))
        for s in suggestions:
            if not str(s.get("file", "")).strip():
                s["file"] = self._find_mentioned_file(
                    str(s.get("description", "")), changed_files
                )
        return PhaseResult(
            items=review_items,
            llm_verdict=metadata.get("verdict") or None,
            llm_reason=metadata.get("reason", ""),
            llm_summary=metadata.get("summary", ""),
            llm_suggestions=suggestions,
            llm_praise=metadata.get("praise", []),
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
    ) -> None:
        self._log_conversation_debug(
            phase_name, messages, turns, phase_result, repo_path,
        )
        if self._conversation_logger is None:
            return
        pr_identifier = self._derive_pr_identifier(repo_path)
        metadata: dict[str, Any] = {
            "model": "code-review:latest",
            "turns": turns,
            "verdict": (
                phase_result.llm_verdict if phase_result else "exhausted"
            ),
            "item_count": (
                len(phase_result.items) if phase_result else 0
            ),
        }
        try:
            self._conversation_logger.log_conversation(
                phase_name=phase_name or "unknown",
                pr_identifier=pr_identifier,
                messages=messages,
                metadata=metadata,
            )
        except Exception:
            logger.warning(
                "Failed to log conversation for phase %s", phase_name,
                exc_info=True,
            )
