"""AgentConversationService — run a multi-turn agentic conversation with tool access."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any

from pr_auto_reviewer.application.commands.run_agent_conversation_command import (
    RunAgentConversationCommand,
)
from pr_auto_reviewer.application.events.conversation_completed_event import (
    ConversationCompletedEvent,
)
from pr_auto_reviewer.application.events.review_turn_parsed_event import (
    ReviewTurnParsedEvent,
)
from pr_auto_reviewer.application.ports.inbound.parse_review_turn_use_case import (
    ParseReviewTurnUseCase,
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
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity

logger = logging.getLogger(__name__)

_FABRICATED_ERROR_PATTERNS: tuple[str, ...] = (
    "file not found",
    "unable to verify",
    "cannot access",
    "could not read",
    "does not exist",
    "not accessible",
    "not found in",
    "could not be found",
    "unable to locate",
)


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
        turn_parser: ParseReviewTurnUseCase,
        event_bus: CommandBusPort | None = None,
        max_turns: int = 10,
        max_empty_responses: int = 3,
        max_unparseable_responses: int = 3,
    ) -> None:
        self._chat_port = chat_port
        self._turn_parser = turn_parser
        self._event_bus = event_bus
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
        )

    def _run(
        self,
        system_prompt: str,
        repo_path: str,
        changed_files: list[str],
        tool_execution: Any,
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

            from pr_auto_reviewer.application.commands.parse_review_turn_command import (
                ParseReviewTurnCommand,
            )

            parsed = self._turn_parser.execute(
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
                        parsed, repo_path
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
        self, parsed: TurnParseResult, repo_path: str
    ) -> PhaseResult:
        """Build a ``PhaseResult`` from parsed turn data, validating against disk."""
        raw_items = parsed.raw_items or []
        metadata = parsed.metadata or {}
        review_items, skip_reasons = self._build_review_items(
            raw_items, repo_path
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

    @classmethod
    def _build_review_items(
        cls,
        item_dicts: list[dict[str, Any]],
        repo_path: str,
    ) -> tuple[list[ReviewItem], list[str]]:
        """Construct ReviewItem domain objects from parsed item dicts.

        Validates that each ``file_path`` exists in the repository;
        hallucinated paths are skipped with a warning.
        """
        repo_root = Path(repo_path) if repo_path else None
        review_items: list[ReviewItem] = []
        skip_reasons: list[str] = []
        for item_dict in item_dicts:
            file_path = str(item_dict.get("file", ""))
            if file_path.startswith(("a/", "b/")):
                file_path = file_path[2:]
            full_path: Path | None = None
            if repo_root is not None and file_path:
                full_path = repo_root / file_path
                if not full_path.exists():
                    reason = f"file not found: {file_path}"
                    logger.warning("Skipping finding — %s", reason)
                    skip_reasons.append(reason)
                    continue
                try:
                    file_path = str(
                        full_path.resolve().relative_to(
                            repo_root.resolve()
                        )
                    )
                except ValueError:
                    pass
            current_code = str(item_dict.get("current_code", ""))
            suggested_fix = str(item_dict.get("suggested_fix", ""))
            line_str = str(item_dict.get("line", ""))
            if full_path is not None and file_path and (
                line_str or current_code
            ):
                file_lines = full_path.read_text().splitlines()
                if line_str:
                    try:
                        line_num = int(line_str)
                        if not (1 <= line_num <= len(file_lines)):
                            reason = (
                                f"line {line_str} out of range in "
                                f"{file_path} ({len(file_lines)} lines)"
                            )
                            logger.warning(
                                "Skipping finding — %s", reason
                            )
                            skip_reasons.append(reason)
                            continue
                        if current_code:
                            actual_line = file_lines[
                                line_num - 1
                            ].strip()
                            if current_code.strip() != actual_line:
                                reason = (
                                    f"code mismatch at "
                                    f"{file_path}:{line_str}"
                                )
                                logger.warning(
                                    "Skipping finding — %s", reason
                                )
                                skip_reasons.append(reason)
                                continue
                    except ValueError:
                        pass
            if (
                repo_root is not None
                and file_path
                and not current_code
                and not suggested_fix
            ):
                reason = f"no code evidence in {file_path}"
                logger.warning("Skipping finding — %s", reason)
                skip_reasons.append(reason)
                continue
            description = str(item_dict.get("description", ""))
            if (
                repo_root is not None
                and file_path
                and not current_code
                and description
            ):
                description_lower = description.lower()
                if any(
                    pattern in description_lower
                    for pattern in _FABRICATED_ERROR_PATTERNS
                ):
                    reason = (
                        f"fabricated narrative in {file_path}: "
                        f"{description[:80]}"
                    )
                    logger.warning(
                        "Skipping finding — %s", reason
                    )
                    skip_reasons.append(reason)
                    continue

            review_item = ReviewItem(
                number=len(review_items) + 1,
                severity=ItemSeverity(
                    str(item_dict.get("severity", "info"))
                ),
                category=IssueCategory.from_value(
                    str(item_dict.get("category", "maintainability"))
                ),
                file_path=file_path,
                description=str(item_dict.get("description", "")),
                line=str(item_dict.get("line", "")),
                current_code=current_code,
                suggested_fix=suggested_fix,
            )
            review_items.append(review_item)

        if skip_reasons:
            logger.info(
                "%d items parsed, %d skipped: %s",
                len(item_dicts),
                len(skip_reasons),
                ", ".join(skip_reasons),
            )
        return review_items, skip_reasons

    def _publish(self, event: Any) -> None:
        """Publish an event to the bus if one is configured."""
        if self._event_bus is not None:
            self._event_bus.dispatch(event)
