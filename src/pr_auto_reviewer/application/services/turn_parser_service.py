"""TurnParserService — parse a single LLM conversation turn into a TurnParseResult."""

from __future__ import annotations

import json
import logging
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
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
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
            metadata = self._extract_verdict_metadata(content, items)
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
                kind=TurnKind.VERDICT,
                raw_items=items,
                metadata=metadata,
            )

        parsed = self._parse_json(content)
        if parsed is None:
            logger.debug("Unparseable content (first 2000 chars): %s", content[:2000])
            return TurnParseResult(kind=TurnKind.UNPARSEABLE)

        target = (
            parsed.get("data")
            if (isinstance(parsed, dict) and isinstance(parsed.get("data"), dict))
            else parsed
        )

        if isinstance(target, dict) and "action" in target:
            raw_args = target.get("args", "")
            if isinstance(raw_args, list):
                args_str = " ".join(str(a) for a in raw_args)
            elif isinstance(raw_args, dict):
                args_str = self._extract_dict_args(
                    str(target["action"]), raw_args
                )
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
            k in target
            for k in (
                "verdict",
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
            items_data = (
                target.get("items")
                or target.get("issues")
                or target.get("findings")
                or []
            )
            raw_items: list[dict[str, Any]] = []
            if isinstance(items_data, list):
                for entry in items_data:
                    if isinstance(entry, dict):
                        raw_items.append(self._parser.normalize_item_dict(entry))
            verdict_val = target.get("verdict", "")
            if not verdict_val:
                verdict_val = self._verdict_for_items(raw_items).value
            metadata = {
                "verdict": self._verdict_str(verdict_val),
                "reason": str(
                    target.get("reason")
                    or target.get("summary", "")
                    or self._reason_for_items(raw_items)
                ),
                "summary": str(
                    target.get("summary", "")
                    or self._summary_for_items(raw_items)
                ),
                "suggestions": self._suggestions_from(target),
                "praise": self._praise_from(target),
            }
            return TurnParseResult(
                kind=TurnKind.VERDICT,
                raw_items=raw_items,
                metadata=metadata,
            )

        if isinstance(parsed, list):
            return TurnParseResult(
                kind=TurnKind.VERDICT,
                raw_items=[
                    self._parser.normalize_item_dict(item)
                    for item in parsed
                    if isinstance(item, dict)
                ],
                metadata={},
            )

        return TurnParseResult(kind=TurnKind.UNPARSEABLE)

    def _extract_verdict_metadata(
        self, content: str, raw_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Extract verdict metadata from a JSON block or markdown in the content."""
        try:
            parsed = json.loads(self._parser.sanitize_json_literals(content))
        except json.JSONDecodeError:
            extracted = self._parser.extract_outermost_json(content)
            if extracted is None:
                return self._extract_verdict_from_markdown(content, raw_items)
            try:
                parsed = json.loads(
                    self._parser.sanitize_json_literals(extracted)
                )
            except json.JSONDecodeError:
                return self._extract_verdict_from_markdown(content, raw_items)
        target = (
            parsed.get("data")
            if (isinstance(parsed, dict) and isinstance(parsed.get("data"), dict))
            else parsed
        )
        if isinstance(target, dict) and any(
            k in target
            for k in (
                "verdict",
                "suggestions",
                "recommendations",
                "improvements",
                "recommended",
                "praise",
                "strengths",
                "positives",
                "reason",
                "summary",
            )
        ):
            verdict_val = target.get("verdict", "")
            if not verdict_val:
                verdict_val = self._verdict_for_items(raw_items).value
            return {
                "verdict": self._verdict_str(verdict_val),
                "reason": str(
                    target.get("reason")
                    or target.get("summary", "")
                    or self._reason_for_items(raw_items)
                ),
                "summary": str(
                    target.get("summary", "")
                    or self._summary_for_items(raw_items)
                ),
                "suggestions": self._suggestions_from(target),
                "praise": self._praise_from(target),
            }
        return self._extract_verdict_from_markdown(content, raw_items)

    def _extract_verdict_from_markdown(
        self, content: str, raw_items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Build metadata from markdown prose, deriving the verdict from items.

        Prose responses rarely carry an explicit verdict section. When
        the parser refuses to extract one, the verdict implied by the
        already-parsed findings is used instead of failing the turn.
        """
        try:
            verdict = self._parser.extract_verdict_md(content)
        except ReviewVerdictError:
            verdict = self._verdict_for_items(raw_items)
        suggestions = self._parser.parse_prose_recommendations(content)
        praise = self._parser.parse_prose_praise(content)
        return {
            "verdict": verdict.value,
            "reason": self._reason_for_items(raw_items),
            "summary": self._summary_for_items(raw_items),
            "suggestions": suggestions,
            "praise": praise,
        }

    def _verdict_for_items(self, raw_items: list[dict[str, Any]]) -> ReviewVerdict:
        """Return the verdict implied by the severities of *raw_items*."""
        blocking = {ItemSeverity.CRITICAL.value, ItemSeverity.MAJOR.value}
        if any(
            str(item.get("severity", "")).lower() in blocking
            for item in raw_items
        ):
            return ReviewVerdict.CHANGES_REQUESTED
        return ReviewVerdict.APPROVED

    def _reason_for_items(self, raw_items: list[dict[str, Any]]) -> str:
        """Return a descriptive reason grounded in the findings."""
        if not raw_items:
            return "No issues found."
        blocking = [
            item for item in raw_items
            if str(item.get("severity", "")).lower() in {"critical", "major"}
        ]
        target_items = blocking if blocking else raw_items
        first = target_items[0]
        desc = str(first.get("description") or "").strip()
        sev = str(first.get("severity") or "issue").lower()
        file_path = str(first.get("file") or first.get("file_path") or "").strip()
        file_str = f" in {file_path}" if file_path else ""
        if desc:
            return f"Identified {sev} issue{file_str}: {desc}"
        return f"Identified {len(raw_items)} potential issue(s)."

    def _summary_for_items(self, raw_items: list[dict[str, Any]]) -> str:
        """Return a detailed summary naming the findings, files, and impact."""
        if not raw_items:
            return ""
        files = sorted({
            str(item.get("file") or item.get("file_path") or "")
            for item in raw_items
            if item.get("file") or item.get("file_path")
        })
        blocking = [
            item for item in raw_items
            if str(item.get("severity", "")).lower() in {"critical", "major"}
        ]
        categories = sorted({
            str(item.get("category", ""))
            for item in raw_items
            if item.get("category")
        })
        cat_str = f" ({', '.join(categories)})" if categories else ""
        if blocking:
            descs = [
                str(b.get("description") or "").strip()
                for b in blocking
                if b.get("description")
            ]
            details = f": {'; '.join(descs[:2])}" if descs else ""
            file_str = f" in {', '.join(files[:3])}" if files else ""
            return (
                f"Identified {len(raw_items)} finding(s){cat_str} with "
                f"{len(blocking)} blocking issue(s){file_str}{details}."
            )
        file_str = f" across {len(files)} file(s)" if files else ""
        return f"Identified {len(raw_items)} non-blocking finding(s){cat_str}{file_str}."

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