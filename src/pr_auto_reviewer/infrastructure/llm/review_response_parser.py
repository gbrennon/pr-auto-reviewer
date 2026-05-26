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

        code_block_match = re.search(
            r"```(?:json)?\s*\n?(.*?)```",
            json_text,
            re.DOTALL,
        )
        if code_block_match:
            inner = code_block_match.group(1).strip()
            json_text = ReviewResponseParser._extract_outermost_json(inner) or json_text
            logger.debug("Extracted JSON from code block (%d chars)", len(json_text))

        try:
            data = json.loads(json_text)
            if isinstance(data, dict):
                logger.debug("Parsed as pure JSON: keys=%s", list(data.keys()))
                return ReviewResponseParser._parse_json(data, model_used)
        except json.JSONDecodeError:
            logger.debug("Pure JSON parse failed, trying extraction from text...")

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
        suggestions = ReviewResponseParser._extract_suggestions_md(raw_text)
        praise = ReviewResponseParser._extract_praise_md(raw_text)

        # the first meaningful paragraph as summary (before any ## heading)
        if not summary and not items:
            first_para = ReviewResponseParser._extract_first_paragraph(raw_text)
            summary = first_para if first_para else raw_text.strip()[:500]

        if verdict == ReviewVerdict.COMMENTED:
            if "commented" not in raw_text[:500].lower():
                verdict = ReviewVerdict.APPROVED

        return CodeReview(
            verdict=verdict,
            summary=summary,
            items=items,
            suggestions=suggestions,
            praise=praise,
            model_used=model_used,
        )

    @staticmethod
    def _extract_outermost_json(text: str) -> str | None:
        """Find the last valid outermost balanced JSON object via brace counting.

        Iterates through each ``{}`` pair in *text* in order and returns the
        **last** one that parses successfully with ``json.loads()``.

        This handles the common case where a base model echoes the prompt
        (which may contain a non-valid JSON template with ``...`` in arrays)
        before generating its actual JSON response — the echoed template is
        skipped and the model's response is returned instead.

        When the model returns a single valid JSON object the behaviour is
        unchanged from the original first-``{}``-wins strategy.
        """
        last_valid: str | None = None
        pos = 0
        while True:
            start = text.find("{", pos)
            if start == -1:
                return last_valid
            depth = 0
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        candidate = text[start : i + 1]
                        try:
                            json.loads(candidate)
                            last_valid = candidate
                            pos = i + 1
                        except json.JSONDecodeError:
                            pos = i + 1
                        break
            else:
                return last_valid

    @staticmethod
    def _parse_json(data: dict, model_used: str) -> CodeReview:
        """Parse JSON format response."""
        issues = data.get("issues", [])
        suggestions = data.get("suggestions", [])
        praise = data.get("praise", [])
        summary = data.get("summary", "")
        reason = data.get("reason") or ""
        if not reason:
            reasons = data.get("reasons")
            if isinstance(reasons, list):
                reason = " ".join(r for r in reasons if isinstance(r, str))
            elif isinstance(reasons, str):
                reason = reasons

        verdict = ReviewResponseParser._resolve_verdict(
            data.get("verdict"), issues,
        )

        _SEVERITY_MAP = {
            "critical": ItemSeverity.CRITICAL,
            "high": ItemSeverity.MAJOR,
            "major": ItemSeverity.MAJOR,
            "medium": ItemSeverity.MINOR,
            "minor": ItemSeverity.MINOR,
            "low": ItemSeverity.INFO,
            "info": ItemSeverity.INFO,
        }

        items = []
        for idx, issue in enumerate(issues, 1):
            severity_str = issue.get("severity", "").strip().lower()
            if severity_str and severity_str in _SEVERITY_MAP:
                severity = _SEVERITY_MAP[severity_str]
            else:
                severity, severity_str = ReviewResponseParser._infer_severity(
                    issue.get("description", "")
                )

            category = (issue.get("type") or "").strip()
            if not category:
                category = ReviewResponseParser._infer_type(
                    issue.get("description", ""), severity_str
                )

            items.append(
                ReviewItem(
                    number=idx,
                    severity=severity,
                    category=category,
                    file_path=issue.get("file"),
                    line=issue.get("line", ""),
                    description=issue.get("description", ""),
                    current_code=issue.get("current_code", ""),
                    suggested_fix=issue.get("suggested_fix", ""),
                )
            )

        enriched_suggestions = []
        for s in suggestions:
            enriched_suggestions.append({
                "file": s.get("file", ""),
                "line": s.get("line", ""),
                "description": s.get("description", ""),
                "current_code": s.get("current_code", ""),
                "suggested_code": s.get("suggested_code", ""),
            })

        return CodeReview(
            verdict=verdict,
            reason=reason,
            summary=summary,
            items=items,
            suggestions=enriched_suggestions,
            praise=praise,
            model_used=model_used,
        )

    @staticmethod
    def _infer_severity(description: str) -> tuple[ItemSeverity, str]:
        """Infer severity from issue description keywords.

        Returns (ItemSeverity, severity_str) so callers can use the string
        for further inference (e.g., type).
        """
        desc = description.lower()
        # Critical keywords
        if any(kw in desc for kw in (
            "security", "injection", "leak", "vulnerability",
            "exploit", "secret", "credential", "xss", "csrf",
            "auth bypass", "hardcoded",
        )):
            return ItemSeverity.CRITICAL, "critical"
        # High keywords
        if any(kw in desc for kw in (
            "crash", "race", "deadlock", "null pointer", "undefined",
            "exception", "unhandled error", "logic bug", "wrong result",
            "data loss", "corruption",
        )):
            return ItemSeverity.MAJOR, "high"
        # Low keywords — docs, style, cosmetic
        if any(kw in desc for kw in (
            "naming", "rename", "typo", "style", "todo",
            "unused", "dead code", "comment", "cosmetic",
            "readability", "whitespace", "documentation",
            "update readme", "add doc", "add documentation",
        )):
            return ItemSeverity.INFO, "low"
        # Default to medium
        return ItemSeverity.MINOR, "medium"

    @staticmethod
    def _infer_type(description: str, severity_str: str) -> str:
        """Infer issue type from description keywords."""
        desc = description.lower()
        if any(kw in desc for kw in (
            "security", "injection", "secret", "leak", "vulnerability",
            "exploit", "credential", "xss", "csrf", "auth bypass",
            "hardcoded",
        )):
            return "security"
        if any(kw in desc for kw in (
            "architecture", "layer", "boundary", "god object",
            "tight coupling", "violation", "adapter", "port",
            "hexagonal",
        )):
            return "architecture"
        if any(kw in desc for kw in (
            "solid", "srp", "single responsib", "open/closed",
            "liskov", "interface seg", "dependency inversion",
        )):
            return "solid"
        if any(kw in desc for kw in (
            "test", "assert", "coverage", "mock", "stub",
            "fixture", "edge case", "boundary",
        )):
            return "test"
        if any(kw in desc for kw in (
            "convention", "style", "formatting", "naming",
            "typo", "rename",
        )):
            return "convention"
        if any(kw in desc for kw in (
            "magic number", "nesting", "duplicate", "duplication",
            "dead code", "unused",
        )):
            return "quality"
        # Default by severity
        if severity_str in ("critical", "high"):
            return "architecture"
        return "quality"



    @staticmethod
    def _resolve_verdict(
        explicit: str | None, issues: list,
    ) -> ReviewVerdict:
        """Resolve verdict — prefer explicit JSON field, fall back to
        deriving from issue severities."""
        if explicit:
            value = explicit.strip().lower()
            if "changes" in value or "request" in value:
                return ReviewVerdict.CHANGES_REQUESTED
            if "approved" in value or value == "approve":
                return ReviewVerdict.APPROVED
            if "commented" in value:
                return ReviewVerdict.COMMENTED
        return ReviewResponseParser._determine_verdict(issues)

    @staticmethod
    def _determine_verdict(issues: list) -> ReviewVerdict:
        """Determine verdict based on issue severities."""
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
        if match:
            value = match.group(1).strip().lower()
            if "changes_requested" in value or "request changes" in value:
                return ReviewVerdict.CHANGES_REQUESTED
            if "approved" in value:
                return ReviewVerdict.APPROVED

        # Try **Verdict:** value (model Modelfile output)
        match = re.search(
            r"\*\*Verdict:\s*\*\*\s*(.+)", raw_text, re.IGNORECASE
        )
        if match:
            value = match.group(1).strip().lower()
            if "changes" in value or "request" in value:
                return ReviewVerdict.CHANGES_REQUESTED
            if "approved" in value or value == "approve":
                return ReviewVerdict.APPROVED
            if "commented" in value:
                return ReviewVerdict.COMMENTED

        match = re.search(r"Verdict:\s*(.+)", raw_text, re.IGNORECASE)
        if match:
            value = match.group(1).strip().lower()
            if "changes" in value or "request" in value:
                return ReviewVerdict.CHANGES_REQUESTED
            if "approved" in value or value == "approve":
                return ReviewVerdict.APPROVED

        return ReviewVerdict.COMMENTED

    @staticmethod
    def _extract_first_paragraph(raw_text: str) -> str | None:
        """Extract text before the first ``##`` heading as a summary."""
        match = re.search(r"^(.+?)\n##\s", raw_text, re.DOTALL)
        if match:
            para = match.group(1).strip()
            if para.lower().startswith("verdict") or para.lower().startswith("**verdict"):
                return None
            return para if len(para) > 20 else None
        return None

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
    def _isolate_section(raw_text: str, heading: str) -> str | None:
        """Return the portion between ``## <heading>`` and the next ``##`` heading."""
        pattern = rf"##\s*{re.escape(heading)}\s*\n(.*?)(?=\n##\s|\Z)"
        match = re.search(pattern, raw_text, re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        body = match.group(1).strip()
        if not body or body.lower() in ("none", "n/a", f"no {heading.lower()}"):
            return None
        return body

    @staticmethod
    def _isolate_items_section(raw_text: str) -> str | None:
        """Return the portion between ## Items and the next ## heading."""
        return ReviewResponseParser._isolate_section(raw_text, "Items")

    @staticmethod
    def _extract_suggestions_md(raw_text: str) -> list[dict]:
        """Fallback: extract suggestions from markdown format.
        
        Expects lines under ``## Suggestions`` or ``### Suggestions``.
        """
        section = ReviewResponseParser._isolate_section(raw_text, "Suggestions")
        if not section:
            return []
        suggestions: list[dict] = []
        for line in section.split("\n"):
            line = line.strip()
            if not line or line.lower().startswith("no suggestion"):
                continue
            entry: dict = {}
            # Numbered: "1. file.py:line description"
            m = re.match(r"^\d+\.\s*(\S+)?:?\s*(\d+\s+)?(.*)", line)
            if m:
                if m.group(1) and ":" in line.split(". ", 1)[1][:5]:
                    entry["file"] = m.group(1)
                    rest = line.split(". ", 1)[1]
                    rest = rest[len(m.group(1)) + 1:].strip()
                    line_m = re.match(r"^(\d+)\s+(.*)", rest)
                    if line_m:
                        entry["line"] = line_m.group(1)
                        entry["description"] = line_m.group(2)
                    else:
                        entry["description"] = rest
                else:
                    entry["description"] = (m.group(3) or line).strip()
            elif line.startswith("- "):
                entry["description"] = line[2:]
            elif line.startswith("* "):
                entry["description"] = line[2:]
            if entry.get("description"):
                suggestions.append(entry)
        return suggestions

    @staticmethod
    def _extract_praise_md(raw_text: str) -> list[dict]:
        """Fallback: extract praise items from markdown format.
        
        Expects lines under ``## Praise`` or ``### Praise``.
        """
        section = ReviewResponseParser._isolate_section(raw_text, "Praise")
        if not section:
            return []
        praise: list[dict] = []
        for line in section.split("\n"):
            line = line.strip()
            if not line or line.lower().startswith("no notable"):
                continue
            if line.startswith("- ") or line.startswith("* "):
                content = line[2:]
                if ":" in content and not content.startswith("http"):
                    file_part, _, desc = content.partition(":")
                    praise.append({
                        "file": file_part.strip(),
                        "description": desc.strip(),
                    })
                else:
                    praise.append({"description": content})
        return praise

    _ITEM_RE_MD = re.compile(
        r"^\s*[-*]\s*\[(?P<severity>critical|major|minor|info)\]\s*"
        r"(?P<category>[^(]+?)\s*"
        r"\((?P<file_path>[^)]*)\)\s*"
        r"(?P<description>.+)$",
        re.IGNORECASE | re.MULTILINE,
    )
