"""IssueContentPreparerService — prepares issue title and body via LLM sub-agent."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pr_auto_reviewer.application.ports.inbound.prepare_issue_content_port import (
    PrepareIssueContentPort,
)
from pr_auto_reviewer.application.ports.outbound.agent_chat_port import (
    AgentChatPort,
)
from pr_auto_reviewer.application.serializers.issue_body_builder import (
    IssueBodyBuilder,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.commands.prepare_issue_content_command import (
    PrepareIssueContentCommand,
)
from pr_auto_reviewer.domain.value_objects.issue_content import IssueContent
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.templates.conversation_renderers import (
    IssueContentSystemRenderer,
    IssueContentUserRenderer,
)

logger = logging.getLogger(__name__)


class IssueContentPreparerService(PrepareIssueContentPort):
    """Prepares structured issue title and body for a review item.

    Delegates to a sub-agent conversation to generate an issue title and
    markdown body with Problem, Rationale, and Acceptance Criteria. Falls
    back to deterministic issue body generation if the model call fails
    or returns unparseable content.
    """

    def __init__(
        self,
        chat_port: AgentChatPort,
        issue_body_builder: IssueBodyBuilder,
    ) -> None:
        self._chat_port = chat_port
        self._issue_body_builder = issue_body_builder
        self._system_renderer = IssueContentSystemRenderer()
        self._user_renderer = IssueContentUserRenderer()

    def execute(self, command: PrepareIssueContentCommand) -> IssueContent:
        """Prepare tracker issue content for the given command."""
        pr_id = command.pr_id
        item = command.item
        messages = [
            self._system_renderer.render(),
            self._user_renderer.render(
                description=item.description,
                file_path=item.file_path or "",
                category=item.category.value,
                severity=item.severity.value,
                pr_identifier=str(pr_id),
            ),
        ]
        try:
            raw_response = self._chat_port.send(messages)
        except Exception:
            logger.warning(
                "Sub-agent issue content preparation failed for item %s on %s",
                item.id,
                pr_id,
                exc_info=True,
            )
            return self._build_fallback(pr_id, item)

        if not raw_response:
            return self._build_fallback(pr_id, item)

        parsed_content = self._parse_issue_content(raw_response)
        if parsed_content is not None:
            return parsed_content

        return self._build_fallback(pr_id, item)

    def _build_fallback(
        self, pr_id: PullRequestId, item: ReviewItem
    ) -> IssueContent:
        title, body = self._issue_body_builder.build(pr_id, item)
        return IssueContent(title=title, body=body)

    @classmethod
    def _parse_issue_content(cls, raw_response: str) -> IssueContent | None:
        raw_json = cls._extract_outermost_json(raw_response)
        if raw_json is None:
            return None
        try:
            payload: Any = json.loads(raw_json)
        except json.JSONDecodeError:
            return None
        if not isinstance(payload, dict):
            return None
        return cls._extract_content_from_payload(payload)

    @staticmethod
    def _extract_content_from_payload(
        payload: dict[str, Any],
    ) -> IssueContent | None:
        title = payload.get("title")
        body = payload.get("body")
        if not isinstance(title, str) or not isinstance(body, str):
            return None
        stripped_title = title.strip()
        stripped_body = body.strip()
        if not stripped_title or not stripped_body:
            return None
        return IssueContent(title=stripped_title, body=stripped_body)

    @classmethod
    def _extract_outermost_json(cls, text: str) -> str | None:
        fence_match = re.search(
            r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE,
        )
        candidates = [fence_match.group(1).strip()] if fence_match else []
        candidates.append(text)
        for candidate in candidates:
            parsed = cls._find_balanced_json(candidate)
            if parsed is not None:
                return parsed
        return None

    @classmethod
    def _find_balanced_json(cls, candidate: str) -> str | None:
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass

        start = candidate.find("{")
        if start == -1:
            return None

        end = cls._find_matching_brace_index(candidate, start)
        if end == -1:
            return None

        substring = candidate[start : end + 1]
        try:
            json.loads(substring)
            return substring
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _find_matching_brace_index(text: str, start: int) -> int:
        depth = 0
        in_string = False
        escape = False
        for i in range(start, len(text)):
            char = text[i]
            in_string, escape, is_literal = (
                IssueContentPreparerService._track_string_state(
                    char, in_string, escape
                )
            )
            if is_literal:
                continue
            depth += IssueContentPreparerService._depth_delta(char)
            if depth == 0 and char == "}":
                return i
        return -1

    @staticmethod
    def _depth_delta(char: str) -> int:
        if char == "{":
            return 1
        if char == "}":
            return -1
        return 0

    @staticmethod
    def _track_string_state(
        char: str, in_string: bool, escape: bool
    ) -> tuple[bool, bool, bool]:
        if escape:
            return in_string, False, True
        if char == "\\":
            return in_string, True, True
        if char == '"':
            return not in_string, False, True
        return in_string, False, in_string
