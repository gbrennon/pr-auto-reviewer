"""TurnParser — parse a single LLM conversation turn into a TurnParseResult."""

from __future__ import annotations

import json
import logging
from typing import Any, ClassVar

from pr_auto_reviewer.application.commands.parse_review_turn_command import (
    ParseReviewTurnCommand,
)
from pr_auto_reviewer.application.ports.inbound.parse_review_turn_use_case import (
    ParseReviewTurnUseCase,
)
from pr_auto_reviewer.domain.agent.tool_call import ToolCall
from pr_auto_reviewer.domain.agent.turn_parse_result import TurnParseResult
from pr_auto_reviewer.application.ports.outbound.response_parser_port import (
    ResponseParserPort,
)

logger = logging.getLogger(__name__)


class TurnParser(ParseReviewTurnUseCase):
    """Parse a raw LLM response into a structured TurnParseResult.

    Extracts item dicts via ``ResponseParserPort.parse_items()`` and
    metadata (verdict, reason, summary, suggestions, praise) from JSON
    blocks. Does NOT validate items against disk — that is the caller's
    responsibility.
    """

    def __init__(self, parser: ResponseParserPort) -> None:
        self._parser = parser

    def execute(self, command: ParseReviewTurnCommand) -> TurnParseResult:
        """Parse *command.content* into a tool-call, verdict, or unparseable result."""
        return self._parse(command.content)

    def _parse(self, content: str) -> TurnParseResult:
        """Parse *content* into a tool-call, verdict, or unparseable result.

        For verdicts, populates ``raw_items`` and ``metadata`` so the
        caller can validate items against the repository.
        """
        items = self._parser.parse_items(content)
        if items:
            metadata = self._extract_verdict_metadata(content)
            return TurnParseResult(
                kind="verdict",
                raw_items=items,
                metadata=metadata,
            )

        parsed = self._parse_json(content)
        if parsed is None:
            return TurnParseResult(kind="unparseable")

        if isinstance(parsed, dict) and "action" in parsed:
            raw_args = parsed.get("args", "")
            if isinstance(raw_args, list):
                args_str = " ".join(str(a) for a in raw_args)
            elif isinstance(raw_args, dict):
                args_str = self._extract_dict_args(
                    str(parsed["action"]), raw_args
                )
            else:
                args_str = str(raw_args)
            return TurnParseResult(
                kind="tool_call",
                tool_call=ToolCall(
                    tool_name=str(parsed["action"]),
                    arguments={"args": args_str},
                ),
            )

        if isinstance(parsed, dict) and "verdict" in parsed:
            items_data = (
                parsed.get("items")
                or parsed.get("issues")
                or parsed.get("findings")
                or []
            )
            metadata = {
                "verdict": str(parsed.get("verdict", "")),
                "reason": str(
                    parsed.get("reason") or parsed.get("summary", "")
                ),
                "summary": str(parsed.get("summary", "")),
                "suggestions": self._normalize_suggestions(
                    parsed.get("suggestions", [])
                ),
                "praise": self._normalize_praise(
                    parsed.get("praise", [])
                ),
            }
            return TurnParseResult(
                kind="verdict",
                raw_items=items_data if isinstance(items_data, list) else [],
                metadata=metadata,
            )

        if isinstance(parsed, list):
            return TurnParseResult(
                kind="verdict",
                raw_items=[],
                metadata={},
            )

        return TurnParseResult(kind="unparseable")

    def _extract_verdict_metadata(self, content: str) -> dict[str, Any]:
        """Extract verdict metadata from a JSON block in the content."""
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
                "reason": str(
                    parsed.get("reason") or parsed.get("summary", "")
                ),
                "summary": str(parsed.get("summary", "")),
                "suggestions": self._normalize_suggestions(
                    parsed.get("suggestions", [])
                ),
                "praise": self._normalize_praise(
                    parsed.get("praise", [])
                ),
            }
        return {}

    def _parse_json(self, content: str) -> Any:
        """Attempt to parse *content* as JSON, with markdown extraction fallback."""
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            extracted = self._parser.extract_outermost_json(content)
            if extracted is not None:
                try:
                    return json.loads(extracted)
                except json.JSONDecodeError:
                    pass
        return None

    _DICT_ARG_KEYS: ClassVar[dict[str, list[str]]] = {
        "read_file": ["file", "file_path"],
        "list_directory": ["path", "directory_path"],
        "search_codebase": ["pattern"],
        "run_git": ["command"],
    }

    @classmethod
    def _extract_dict_args(
        cls, action: str, raw_args: dict[str, Any]
    ) -> str:
        """Extract args from dict-format tool calls the LLM sometimes sends."""
        for key in cls._DICT_ARG_KEYS.get(action, []):
            if key in raw_args:
                return str(raw_args[key])
        for fallback in (
            "command", "path", "pattern", "file", "file_path",
            "directory_path", "query",
        ):
            if fallback in raw_args:
                return str(raw_args[fallback])
        return str(raw_args)

    @staticmethod
    def _normalize_suggestions(raw: Any) -> list[dict[str, str]]:
        """Normalize suggestions from the LLM into a consistent format."""
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
        """Normalize praise items from the LLM into a consistent format."""
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
