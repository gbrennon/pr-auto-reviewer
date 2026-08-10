"""AgentConversationService — run a multi-turn agentic conversation with tool access."""

from __future__ import annotations

import json
import logging
import tempfile
from typing import Any

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
from pr_auto_reviewer.application.ports.inbound.run_agent_conversation_use_case import (
    RunAgentConversationUseCase,
)
from pr_auto_reviewer.application.ports.outbound.agent_chat_port import (
    AgentChatPort,
)
from pr_auto_reviewer.application.ports.outbound.command_bus_port import (
    CommandBusPort,
)
from pr_auto_reviewer.domain.agent.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.domain.agent.phase_result import PhaseResult
from pr_auto_reviewer.domain.agent.turn_parse_result import TurnParseResult
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.domain.services.review_item_factory import (
    ReviewItemFactory,
)

logger = logging.getLogger(__name__)



class AgentConversationService(RunAgentConversationUseCase):
    """Run a multi-turn agentic conversation with tool access.

    Orchestrates the loop: send messages → parse response → execute
    tools → append results → repeat until verdict or exhaustion.
    """

    _MAX_TURNS = 10
    _MAX_EMPTY_RESPONSES = 3
    _MAX_UNPARSEABLE_RESPONSES = 3

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
        self._max_turns = max_turns
        self._max_empty_responses = max_empty_responses
        self._max_unparseable_responses = max_unparseable_responses

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
        )
    def _run(
        self,
        system_prompt: str,
        repo_path: str,
        changed_files: list[str],
        tool_execution: Any,
        phase_name: str = "",
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

        empty_consecutive = 0
        unparseable_consecutive = 0
        tool_calls = 0
        for turn in range(self._max_turns):
            logger.debug("Turn %d/%d", turn + 1, self._max_turns)
            content = self._chat_port.send(messages)
            if not content:
                empty_consecutive += 1
                if empty_consecutive >= self._max_empty_responses:
                    raise LlmUnavailableError(
                        f"LLM returned empty response {empty_consecutive} "
                        f"consecutive times at turn {turn + 1}"
                    )
                logger.debug(
                    "Empty response at turn %d; reprompting", turn + 1
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

            empty_consecutive = 0

            parsed = self._command_bus.dispatch(
                ParseReviewTurnCommand(content=content)
            )
            self._publish(ReviewTurnParsedEvent(
                turn_number=turn + 1, result=parsed
            ))

            if parsed.kind == "unparseable":
                unparseable_consecutive += 1
                if (
                    unparseable_consecutive
                    >= self._max_unparseable_responses
                ):
                    raise LlmUnavailableError(
                        f"LLM returned unparseable response "
                        f"{unparseable_consecutive} consecutive times "
                        f"at turn {turn + 1}"
                    )
                logger.debug(
                    "Unparseable response at turn %d; reprompting",
                    turn + 1,
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
            unparseable_consecutive = 0

            messages.append(ConversationMessage(
                role="assistant", content=content
            ))

            if parsed.kind == "verdict":
                if tool_calls > 0:
                    logger.debug("Got verdict at turn %d", turn + 1)
                    phase_result = self._build_phase_result(
                        parsed, repo_path, changed_files
                    )
                    self._log_conversation(
                        phase_name, messages, turn + 1, phase_result,
                        repo_path=repo_path,
                    )
                    self._publish(ConversationCompletedEvent(
                        phase_result=phase_result
                    ))
                    return phase_result
                logger.debug(
                    "Verdict at turn %d with no tool exploration; "
                    "demanding exploration",
                    turn + 1,
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

            if parsed.kind == "tool_call" and parsed.tool_call is not None:
                tool_call = parsed.tool_call
                logger.debug(
                    "Tool call — action=%s args=%s",
                    tool_call.tool_name,
                    str(tool_call.arguments)[:200],
                )
                result = tool_execution.execute_tool(tool_call)
                tool_calls += 1
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
        self._log_conversation(
            phase_name, messages, self._max_turns, None,
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
            f"Phase exceeded max turns ({self._max_turns}) without a verdict. "
            f"Full conversation dumped to {dump_path}"
        )

    def _build_phase_result(
        self, parsed: TurnParseResult, repo_path: str, changed_files: list[str]
    ) -> PhaseResult:
        """Build a ``PhaseResult`` from parsed turn data, validating against disk."""
        raw_items = parsed.raw_items or []
        metadata = parsed.metadata or {}
        review_items, skip_reasons = ReviewItemFactory().create(
            raw_items, repo_path, changed_files
        )
        return PhaseResult(
            items=review_items,
            llm_verdict=metadata.get("verdict") or None,
            llm_reason=metadata.get("reason", ""),
            llm_summary=metadata.get("summary", ""),
            llm_suggestions=metadata.get("suggestions", []),
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
        repo_path: str = "",
    ) -> None:
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

    @staticmethod
    def _derive_pr_identifier(repo_path: str) -> str:
        if not repo_path:
            return "unknown"
        import re
        match = re.search(r"/repos/([^/]+)_([^/]+)_(\d+)$", repo_path)
        if match:
            return f"{match.group(1)}/{match.group(2)}#{match.group(3)}"
        return repo_path.rsplit("/", 1)[-1]
