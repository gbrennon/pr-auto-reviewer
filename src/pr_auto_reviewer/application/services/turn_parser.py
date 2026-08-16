"""TurnParser — parse a single LLM conversation turn into a TurnParseResult."""

from __future__ import annotations

import json
import logging
from typing import Any, ClassVar

from pr_auto_reviewer.domain.messages.commands.parse_review_turn_command import (
    ParseReviewTurnCommand,
)
from pr_auto_reviewer.application.ports.inbound.parse_review_turn_use_case import (
    ParseReviewTurnUseCase,
)
from pr_auto_reviewer.application.ports.outbound.response_parser_port import (
    ResponseParserPort,
)
from pr_auto_reviewer.domain.agent.tool_call import ToolCall
from pr_auto_reviewer.domain.agent.turn_parse_result import TurnParseResult
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict

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

    def _verdict_str(self, value: object) -> str:
        coerced = ReviewVerdict.coerce(value)
        return coerced.value if coerced is not None else str(value or "")

    def _suggestions_from(self, parsed: dict[str, Any]) -> list[dict[str, str]]:
        raw = (
            parsed.get("suggestions")
            or parsed.get("recommendations")
            or parsed.get("improvements")
            or parsed.get("recommended")
            or []
        )
        if isinstance(raw, dict):
            raw = raw.get("enhancements") or raw.get("items") or []
        combined = self._normalize_suggestions(raw)
        combined.extend(self._string_item_suggestions(parsed))
        seen: set[str] = set()
        dedup: list[dict[str, str]] = []
        for s in combined:
            desc = s.get("description", "")
            if desc in seen:
                continue
            seen.add(desc)
            dedup.append(s)
        return dedup

    def _praise_from(self, parsed: dict[str, Any]) -> list[dict[str, str]]:
        raw = parsed.get("praise") or parsed.get("strengths") or parsed.get("positives") or []
        return self._normalize_praise(raw)

    def _string_item_suggestions(self, parsed: dict[str, Any]) -> list[dict[str, str]]:
        candidates = (
            parsed.get("items") or parsed.get("issues") or parsed.get("findings") or []
        )
        results: list[dict[str, str]] = []
        if not isinstance(candidates, list):
            return results
        for entry in candidates:
            if isinstance(entry, str) and entry.strip():
                results.append({"file": "", "line": "", "description": entry.strip()})
        return results

    def _parse(self, content: str) -> TurnParseResult:
        """Parse *content* into a tool-call, verdict, or unparseable result.

        For verdicts, populates ``raw_items`` and ``metadata`` so the
        caller can validate items against the repository.
        """
        items = self._parser.parse_items(content)
        logger.debug("_parse: parse_items returned %d items", len(items))
        if items:
            metadata = self._extract_verdict_metadata(content)
            observations = self._parser.parse_item_observations(content)
            existing = metadata.get("suggestions") or []
            combined = list(existing)
            keys = {
                (str(s.get("file") or ""), str(s.get("description") or ""))
                for s in combined
            }
            for obs in observations:
                key = (str(obs.get("file") or ""), str(obs.get("description") or ""))
                if key not in keys:
                    keys.add(key)
                    combined.append(obs)
            metadata["suggestions"] = combined
            return TurnParseResult(
                kind="verdict",
                raw_items=items,
                metadata=metadata,
            )

        parsed = self._parse_json(content)
        if parsed is None:
            logger.debug("Unparseable content (first 2000 chars): %s", content[:2000])
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
                "verdict": self._verdict_str(parsed.get("verdict", "")),
                "reason": str(
                    parsed.get("reason") or parsed.get("summary", "")
                ),
                "summary": str(parsed.get("summary", "")),
                "suggestions": self._suggestions_from(parsed),
                "praise": self._praise_from(parsed),
            }
            raw_items: list[dict[str, Any]] = []
            if isinstance(items_data, list):
                for entry in items_data:
                    if isinstance(entry, dict):
                        raw_items.append(self._parser._normalize_item_dict(entry))
            return TurnParseResult(
                kind="verdict",
                raw_items=raw_items,
                metadata=metadata,
            )

        if isinstance(parsed, list):
            return TurnParseResult(
                kind="verdict",
                raw_items=[
                    self._parser._normalize_item_dict(item)
                    for item in parsed
                    if isinstance(item, dict)
                ],
                metadata={},
            )

        return TurnParseResult(kind="unparseable")

    def _extract_verdict_metadata(self, content: str) -> dict[str, Any]:
        """Extract verdict metadata from a JSON block or markdown in the content."""
        try:
            parsed = json.loads(self._parser._sanitize_json_literals(content))
        except json.JSONDecodeError:
            extracted = self._parser.extract_outermost_json(content)
            if extracted is None:
                return self._extract_verdict_from_markdown(content)
            try:
                parsed = json.loads(
                    self._parser._sanitize_json_literals(extracted)
                )
            except json.JSONDecodeError:
                return self._extract_verdict_from_markdown(content)
        if isinstance(parsed, dict) and "verdict" in parsed:
            return {
                "verdict": self._verdict_str(parsed.get("verdict", "")),
                "reason": str(
                    parsed.get("reason") or parsed.get("summary", "")
                ),
                "summary": str(parsed.get("summary", "")),
                "suggestions": self._suggestions_from(parsed),
                "praise": self._praise_from(parsed),
            }
        return self._extract_verdict_from_markdown(content)

    def _extract_verdict_from_markdown(self, content: str) -> dict[str, Any]:
        verdict = self._parser._extract_verdict_md(content)
        suggestions = self._parser.parse_prose_recommendations(content)
        praise = self._parser.parse_prose_praise(content)
        return {
            "verdict": verdict.value,
            "reason": "",
            "summary": "",
            "suggestions": suggestions,
            "praise": praise,
        }

    def _parse_json(self, content: str) -> Any:
        """Attempt to parse *content* as JSON, with markdown extraction fallback."""
        try:
            return json.loads(self._parser._sanitize_json_literals(content))
        except json.JSONDecodeError:
            extracted = self._parser.extract_outermost_json(content)
            if extracted is not None:
                try:
                    return json.loads(
                        self._parser._sanitize_json_literals(extracted)
                    )
                except json.JSONDecodeError:
                    pass
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
                })
            elif isinstance(entry, str):
                result.append({
                    "file": "",
                    "line": "",
                    "description": entry,
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
