"""ReviewResponseParser — parses raw LLM text into a CodeReview domain object."""

from __future__ import annotations

import json
import logging
import re

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict

logger = logging.getLogger(__name__)


class ReviewResponseParser:
    """Parse the raw LLM text into a CodeReview domain object."""

    _ITEM_RE = re.compile(
        r"^\s*[-*]\s*"
        r"\"file\":\s*\"(?P<file>[^\"]+)\",\s*"
        r"\"line\":\s*\"(?P<line>[^\"]+)\",\s*"
        r"\"severity\":\s*\"(?P<severity>[^\"]+)\",\s*"
        r"\"type\":\s*\"(?P<type>[^\"]+)\",\s*"
        r"\"description\":\s*\"(?P<description>[^\"]+)\"",
        re.IGNORECASE | re.MULTILINE,
    )

    @staticmethod
    def parse(raw_text: str, model_used: str) -> CodeReview:
        json_text = raw_text.strip()

        # 1. Try markdown code blocks first (```json ... ``` or ``` ... ```)
        code_block_match = re.search(
            r"```(?:json)?\s*\n?(.*?)```",
            json_text,
            re.DOTALL,
        )
        if code_block_match:
            inner = code_block_match.group(1).strip()
            json_text = ReviewResponseParser._extract_outermost_json(inner) or json_text
            logger.debug("Extracted JSON from code block (%d chars)", len(json_text))

        # 2. Try to parse as JSON
        try:
            data = json.loads(json_text)
            if isinstance(data, dict):
                logger.debug("Parsed as pure JSON: keys=%s", list(data.keys()))
                return ReviewResponseParser._parse_json(data, model_used)
        except json.JSONDecodeError:
            logger.debug("Pure JSON parse failed, trying extraction from text...")

        # 3. Raw text wasn't pure JSON — try extracting a JSON object from it
        extracted = ReviewResponseParser._extract_outermost_json(json_text)
        if extracted is not None:
            try:
                data = json.loads(extracted)
                if isinstance(data, dict):
                    logger.debug("Extracted JSON from text (%d chars), keys=%s",
                                 len(extracted), list(data.keys()))
                    return ReviewResponseParser._parse_json(data, model_used)
            except json.JSONDecodeError:
                logger.debug("Extracted text was not valid JSON")

        # 4. Fall back to markdown parsing (old format)
        logger.warning(
            "Falling back to markdown parser — dumping raw text to "
            "/tmp/ollama_raw_response.txt"
        )
        try:
            with open("/tmp/ollama_raw_response.txt", "w") as f:
                f.write(raw_text)
        except OSError:
            pass
        verdict = ReviewResponseParser._extract_verdict_md(raw_text)
        summary = ReviewResponseParser._extract_summary_md(raw_text)
        items = ReviewResponseParser._extract_items_md(raw_text)

        # If the markdown parser also found nothing structured, use the
        # raw LLM response as the summary so the review comment is not empty.
        if not summary and not items:
            summary = raw_text.strip()

        return CodeReview(
            verdict=verdict,
            summary=summary,
            items=items,
            model_used=model_used,
        )

    @staticmethod
    def _extract_outermost_json(text: str) -> str | None:
        """Find the outermost balanced JSON object via brace counting.

        Avoids the ``\\{.*?\\}`` trap where a non-greedy regex stops at the
        first ``}`` inside a nested object (e.g. an issue dict inside the
        ``"issues"`` array).
        """
        start = text.find("{")
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return text[start : i + 1]
        return None

    @staticmethod
    def _parse_json(data: dict, model_used: str) -> CodeReview:
        """Parse JSON format response."""
        # Determine verdict from issues
        issues = data.get("issues", [])
        suggestions = data.get("suggestions", [])
        praise = data.get("praise", [])
        summary = data.get("summary", "")

        verdict = ReviewResponseParser._determine_verdict(issues)

        # Map severity strings to ItemSeverity enum
        _SEVERITY_MAP = {
            "critical": ItemSeverity.CRITICAL,
            "high": ItemSeverity.MAJOR,
            "major": ItemSeverity.MAJOR,
            "medium": ItemSeverity.MINOR,
            "minor": ItemSeverity.MINOR,
            "low": ItemSeverity.INFO,
            "info": ItemSeverity.INFO,
        }

        # Convert JSON items to ReviewItem objects
        items = []
        for idx, issue in enumerate(issues, 1):
            severity_str = issue.get("severity", "info").lower()
            severity = _SEVERITY_MAP.get(severity_str, ItemSeverity.INFO)

            items.append(
                ReviewItem(
                    number=idx,
                    severity=severity,
                    category=issue.get("type", ""),
                    file_path=issue.get("file"),
                    description=issue.get("description", ""),
                )
            )

        return CodeReview(
            verdict=verdict,
            summary=summary,
            items=items,
            model_used=model_used,
        )


    @staticmethod
    def _determine_verdict(issues: list) -> ReviewVerdict:
        """Determine verdict based on issues."""
        for issue in issues:
            severity = issue.get("severity", "").lower()
            if severity in ("critical", "high"):
                return ReviewVerdict.CHANGES_REQUESTED
        return ReviewVerdict.APPROVED

    @staticmethod
    def _extract_verdict_md(raw_text: str) -> ReviewVerdict:
        """Fallback: extract verdict from markdown format."""
        match = re.search(
            r"##\s*Verdict\s*\n\s*(.+)", raw_text, re.IGNORECASE
        )
        if not match:
            return ReviewVerdict.COMMENTED

        value = match.group(1).strip().lower()
        if "changes_requested" in value or "request changes" in value:
            return ReviewVerdict.CHANGES_REQUESTED
        if "approved" in value:
            return ReviewVerdict.APPROVED
        return ReviewVerdict.COMMENTED

    @staticmethod
    def _extract_summary_md(raw_text: str) -> str:
        """Fallback: extract summary from markdown format."""
        pattern = r"##\s*Summary\s*\n(.*?)(?=##\s*|\Z)"
        match = re.search(pattern, raw_text, re.IGNORECASE | re.DOTALL)
        if not match:
            return ""
        return match.group(1).strip()

    @staticmethod
    def _extract_items_md(raw_text: str) -> list[ReviewItem]:
        """Fallback: extract items from markdown format."""
        items_section = ReviewResponseParser._isolate_items_section(raw_text)
        if not items_section:
            return []

        items: list[ReviewItem] = []
        for idx, match in enumerate(
            ReviewResponseParser._ITEM_RE_MD.finditer(items_section),
            start=1,
        ):
            severity_str = match.group("severity").lower()
            try:
                severity = ItemSeverity(severity_str)
            except ValueError:
                severity = ItemSeverity.INFO

            file_path = match.group("file_path").strip() or None

            items.append(
                ReviewItem(
                    number=idx,
                    severity=severity,
                    category=match.group("category").strip(),
                    file_path=file_path,
                    description=match.group("description").strip(),
                )
            )

        return items

    @staticmethod
    def _isolate_items_section(raw_text: str) -> str | None:
        """Return the portion between ## Items and the next ## heading."""
        match = re.search(
            r"##\s*Items\s*\n(.*?)(?=\n##\s|\Z)",
            raw_text,
            re.IGNORECASE | re.DOTALL,
        )
        if not match:
            return None

        body = match.group(1).strip()
        if not body or body.lower() in ("none", "n/a", "no items"):
            return None
        return body

    _ITEM_RE_MD = re.compile(
        r"^\s*[-*]\s*\[(?P<severity>critical|major|minor|info)\]\s*"
        r"(?P<category>[^(]+?)\s*"
        r"\((?P<file_path>[^)]*)\)\s*"
        r"(?P<description>.+)$",
        re.IGNORECASE | re.MULTILINE,
    )
