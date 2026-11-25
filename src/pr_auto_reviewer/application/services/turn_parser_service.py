"""TurnParserService — parse a single LLM conversation turn into a TurnParseResult."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, ClassVar

from pr_auto_reviewer.application.ports.inbound.parse_review_turn_port import (
    ParseReviewTurnPort,
)
from pr_auto_reviewer.application.ports.outbound.response_parser_port import (
    ResponseParserPort,
)
from pr_auto_reviewer.domain.exceptions.review_verdict_error import (
    ReviewVerdictError,
)
from pr_auto_reviewer.domain.messages.commands.parse_review_turn_command import (
    ParseReviewTurnCommand,
)
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.domain.value_objects.tool_call import ToolCall
from pr_auto_reviewer.domain.value_objects.turn_kind import TurnKind
from pr_auto_reviewer.domain.value_objects.turn_parse_result import TurnParseResult

logger = logging.getLogger(__name__)


class TurnParserService(ParseReviewTurnPort):
    """Parse a raw LLM response into a structured TurnParseResult.

    Extracts item dicts via ``ResponseParserPort.parse_items()`` and
    metadata (verdict, reason, summary, suggestions, praise) from JSON
    blocks. Does NOT validate items against disk — that is the caller's
    responsibility.
    """

    _DICT_ARG_KEYS: ClassVar[dict[str, list[str]]] = {
        "read_file": ["file", "file_path"],
        "list_directory": ["path", "directory_path"],
        "search_codebase": ["pattern"],
        "run_git": ["command"],
    }

    def __init__(self, parser: ResponseParserPort) -> None:
        self._parser = parser

    def execute(self, command: ParseReviewTurnCommand) -> TurnParseResult:
        """Parse *command.content* into a tool-call, verdict, or unparseable result."""
        return self._parse(command.content)

    def _provided_collection(
        self, data: dict[str, Any], keys: tuple[str, ...], label: str,
    ) -> list[Any]:
        supplied = [key for key in keys if key in data]
        if len(supplied) != 1 or not isinstance(data[supplied[0]], list):
            raise ReviewVerdictError(
                f"Review output must supply exactly one list-valued {label} collection."
            )
        return data[supplied[0]]

    def _normalize_items(self, raw: list[Any]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for entry in raw:
            if not isinstance(entry, dict):
                raise ReviewVerdictError("Each review item must be an object.")
            normalized.append(self._parser.normalize_item_dict(entry))
        return normalized

    def _normalize_collection(
        self, raw: list[Any], label: str,
    ) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for entry in raw:
            if isinstance(entry, str):
                description = entry.strip()
                values: dict[str, Any] = {}
            elif isinstance(entry, dict):
                value = entry.get("description")
                if not isinstance(value, str):
                    raise ReviewVerdictError(
                        f"Each {label} entry must supply a string description."
                    )
                description = value.strip()
                values = entry
            else:
                raise ReviewVerdictError(
                    f"Each {label} entry must be a string or object."
                )
            if not description:
                raise ReviewVerdictError(
                    f"Each {label} entry must have a non-empty description."
                )
            current_code = values.get("current_code", values.get("current", ""))
            suggested_fix = values.get(
                "suggested_fix", values.get("suggested_code", "")
            )
            if not isinstance(current_code, str) or not isinstance(suggested_fix, str):
                raise ReviewVerdictError(
                    f"Each {label} code field must be a string."
                )
            normalized.append({
                "file": str(values.get("file") or values.get("file_path") or ""),
                "line": str(values.get("line") or ""),
                "description": description,
                "current_code": current_code,
                "suggested_fix": suggested_fix,
            })
        return normalized

    def _metadata_from_dict(
        self, target: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        verdict = ReviewVerdict.coerce(target.get("verdict"))
        if verdict is not ReviewVerdict.APPROVED and verdict is not ReviewVerdict.CHANGES_REQUESTED:
            raise ReviewVerdictError(
                "Review output must contain an explicit APPROVED or CHANGES_REQUESTED verdict."
            )
        reason = target.get("reason")
        summary = target.get("summary")
        if not isinstance(reason, str) or not reason.strip():
            raise ReviewVerdictError(
                "Review output must contain a non-empty explicit reason."
            )
        if not isinstance(summary, str) or not summary.strip():
            raise ReviewVerdictError(
                "Review output must contain a non-empty explicit summary."
            )
        raw_items = self._provided_collection(
            target, ("items", "issues", "findings"), "findings"
        )
        raw_suggestions = self._provided_collection(
            target,
            ("suggestions", "recommendations", "improvements", "recommended"),
            "suggestions",
        )
        raw_praise = self._provided_collection(
            target, ("praise", "strengths", "positives"), "praise"
        )
        items = self._normalize_items(raw_items)
        metadata = {
            "verdict": verdict.value,
            "reason": reason.strip(),
            "summary": summary.strip(),
            "suggestions": self._normalize_collection(
                raw_suggestions, "suggestions"
            ),
            "praise": self._normalize_collection(raw_praise, "praise"),
        }
        return items, metadata

    def _parse(self, content: str) -> TurnParseResult:
        """Parse *content* into a tool-call, verdict, or unparseable result."""
        try:
            extracted_items = self._parser.parse_items(content)
        except (ReviewVerdictError, ValueError):
            return TurnParseResult(kind=TurnKind.UNPARSEABLE)
        parsed = self._parse_json(content)
        target = (
            parsed.get("data")
            if isinstance(parsed, dict) and isinstance(parsed.get("data"), dict)
            else parsed
        )
        if isinstance(target, dict) and "action" in target:
            raw_args = target.get("args", "")
            if isinstance(raw_args, list):
                args_str = " ".join(str(a) for a in raw_args)
            elif isinstance(raw_args, dict):
                args_str = self._extract_dict_args(str(target["action"]), raw_args)
            else:
                args_str = str(raw_args)
            return TurnParseResult(
                kind=TurnKind.TOOL_CALL,
                tool_call=ToolCall(
                    tool_name=str(target["action"]),
                    arguments={"args": args_str},
                ),
            )
        if isinstance(target, dict) and any(
            key in target
            for key in (
                "verdict",
                "reason",
                "summary",
                "items",
                "issues",
                "findings",
                "suggestions",
                "recommendations",
                "improvements",
                "recommended",
                "praise",
                "strengths",
                "positives",
            )
        ):
            try:
                raw_items, metadata = self._metadata_from_dict(target)
            except ReviewVerdictError:
                return TurnParseResult(kind=TurnKind.UNPARSEABLE)
            return TurnParseResult(
                kind=TurnKind.VERDICT,
                raw_items=raw_items,
                metadata=metadata,
            )
        if isinstance(parsed, list):
            return TurnParseResult(kind=TurnKind.UNPARSEABLE)
        try:
            raw_items, metadata = self._extract_verdict_metadata(
                content, extracted_items
            )
        except (ReviewVerdictError, ValueError):
            return TurnParseResult(kind=TurnKind.UNPARSEABLE)
        return TurnParseResult(
            kind=TurnKind.VERDICT,
            raw_items=raw_items,
            metadata=metadata,
        )

    def _extract_verdict_metadata(
        self, content: str, raw_items: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Extract and strictly validate metadata from JSON or markdown."""
        parsed = self._parse_json(content)
        if isinstance(parsed, dict):
            target = (
                parsed.get("data")
                if isinstance(parsed.get("data"), dict)
                else parsed
            )
            if isinstance(target, dict):
                return self._metadata_from_dict(target)
        if isinstance(parsed, list):
            raise ReviewVerdictError(
                "A list of findings is not a completed review envelope."
            )
        return self._extract_verdict_from_markdown(content, raw_items)

    def _extract_verdict_from_markdown(
        self, content: str, raw_items: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Extract and strictly validate an explicit markdown envelope."""
        required_sections = (
            r"(?im)^##\s+(?:Items|Issues|Findings)\b",
            r"(?im)^##\s+Suggestions\b",
            r"(?im)^##\s+Praise\b",
        )
        if any(re.search(section, content) is None for section in required_sections):
            raise ReviewVerdictError(
                "Markdown review output must contain explicit collections."
            )
        verdict = self._parser.extract_verdict_md(content)
        reason_match = re.search(
            r"(?im)^\s*(?:\*\*Reason:\s*\*\*|Reason:)\s*(.+)$",
            content,
        )
        summary_match = re.search(
            r"(?is)^##\s*Summary\s*\n(.*?)(?=^##\s|\Z)",
            content,
            re.MULTILINE,
        )
        reason = reason_match.group(1).strip() if reason_match else ""
        summary = summary_match.group(1).strip() if summary_match else ""
        suggestions = self._parser.parse_prose_recommendations(content)
        praise = self._parser.parse_prose_praise(content)
        target = {
            "verdict": verdict.value,
            "reason": reason,
            "summary": summary,
            "items": raw_items,
            "suggestions": suggestions,
            "praise": praise,
        }
        return self._metadata_from_dict(target)

    def _parse_json(self, content: str) -> Any:
        """Attempt to parse *content* as JSON, with markdown extraction fallback."""
        try:
            return json.loads(self._parser.sanitize_json_literals(content))
        except json.JSONDecodeError:
            extracted = self._parser.extract_outermost_json(content)
            if extracted is not None:
                try:
                    return json.loads(
                        self._parser.sanitize_json_literals(extracted)
                    )
                except json.JSONDecodeError:
                    pass
        return None

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

    def _normalize_suggestions(self, raw: Any) -> list[dict[str, str]]:
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
                    "current_code": str(entry.get("current_code", entry.get("current", ""))),
                    "suggested_fix": str(entry.get("suggested_fix", entry.get("suggested_code", ""))),
                })
            elif isinstance(entry, str):
                result.append({
                    "file": "",
                    "line": "",
                    "description": entry,
                    "current_code": "",
                    "suggested_fix": "",
                })
        return result

    def _normalize_praise(self, raw: Any) -> list[dict[str, str]]:
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