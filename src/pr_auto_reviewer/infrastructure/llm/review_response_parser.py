"""Parse LLM review responses into domain objects."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.entities.review_praise import ReviewPraise
from pr_auto_reviewer.domain.entities.review_suggestion import ReviewSuggestion
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
logger = logging.getLogger(__name__)


class ReviewResponseParser:
    """Parse the raw LLM text into a CodeReview domain object."""

    _STOP_TOKENS = ("<|im_end|>", "<｜end▁of▁thinking｜>")

    def __init__(self) -> None:
        pass

    def parse(self, content: str, model: str) -> CodeReview:
        cleaned = self._clean_response(content)
        try:
            data = json.loads(cleaned)
            return self._code_review_from_dict(data, model)
        except (json.JSONDecodeError, ValueError):
            logger.debug("parse: JSON decode failed, trying text extraction")
        extracted = self.extract_outermost_json(cleaned)
        if extracted is not None:
            try:
                data = json.loads(extracted)
                return self._code_review_from_dict(data, model)
            except (json.JSONDecodeError, ValueError):
                logger.debug("parse: extracted JSON decode also failed")
        return self._parse_markdown_fallback(content, model)

    @classmethod
    def _parse_markdown_fallback(cls, content: str, model: str) -> CodeReview:
        verdict = ReviewResponseParser._extract_verdict_md(content)
        summary = ReviewResponseParser._extract_summary_md(content)
        if not summary:
            first_para = ReviewResponseParser._extract_first_paragraph(content)
            summary = first_para if first_para else content.strip()[:500]
        items_data = ReviewResponseParser._parse_markdown_items(content)
        return CodeReview(
            verdict=verdict,
            reason="",
            summary=summary,
            items=items_data,
            suggestions=[],
            praise=[],
            model_used=model,
        )

    @classmethod
    def _parse_markdown_items(cls, content: str) -> list[ReviewItem]:
        pattern = re.compile(
            r"^-\s*\[(\w+)\]\s+(\w+)\s+\(([^)]+)\)\s+(.+)$",
            re.MULTILINE,
        )
        items: list[ReviewItem] = []
        for i, match in enumerate(pattern.finditer(content), 1):
            severity_raw, category_raw, file_path, description = match.groups()
            items.append(
                ReviewItem(
                    number=i,
                    severity=ItemSeverity.from_value(severity_raw),
                    category=IssueCategory.from_value(category_raw),
                    file_path=file_path.strip(),
                    description=description.strip(),
                    line="",
                    current_code="",
                    suggested_fix="",
                )
            )
        return items

    _IMPROVEMENT_SECTION = re.compile(
        r"(?:###|\*\*)\s*[^\w]*(?:\*\*)?\s*(?:Potential\s+Improvements?|Issues|Problems?|Concerns?|Considerations?\s+for\s+Robustness|Recommendations?|Suggestions?)\s*(?:\*\*)?[^\w]*\s*\n+(.*?)(?=\n(?:###|\*\*|---)|\Z)",
        re.IGNORECASE | re.DOTALL,
    )

    _NUMBERED_ITEM = re.compile(
        r"^\d+\.\s*\*?\*?(.+?)\*?\*?\s*$",
        re.MULTILINE,
    )

    _BULLET_ITEM = re.compile(
        r"^[-*]\s+\*?\*?(.+?)\*?\*?\s*$",
        re.MULTILINE,
    )

    @classmethod
    def _parse_prose_items(cls, content: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for match in cls._IMPROVEMENT_SECTION.finditer(content):
            section_body = match.group(1)
            section_items: list[dict[str, Any]] = []
            for item_match in cls._NUMBERED_ITEM.finditer(section_body):
                title = item_match.group(1).strip().rstrip("*:").strip()
                if len(title) > 10:
                    section_items.append(
                        {
                            "file": "",
                            "severity": "minor",
                            "category": "maintainability",
                            "description": title,
                            "line": "",
                            "current_code": "",
                            "suggested_fix": "",
                        }
                    )
            if not section_items:
                for item_match in cls._BULLET_ITEM.finditer(section_body):
                    title = item_match.group(1).strip().rstrip("*:").strip()
                    if len(title) > 10:
                        section_items.append(
                            {
                                "file": "",
                                "severity": "minor",
                                "category": "maintainability",
                                "description": title,
                                "line": "",
                                "current_code": "",
                                "suggested_fix": "",
                            }
                        )
            items.extend(section_items)
        return items

    @classmethod
    def _extract_verdict_md(cls, raw_text: str) -> ReviewVerdict:
        match = re.search(r"##\s*Verdict\s*\n\s*(.+)", raw_text, re.IGNORECASE)
        if match:
            value = match.group(1).strip().lower()
            if "changes_requested" in value or "request changes" in value:
                return ReviewVerdict.CHANGES_REQUESTED
            if "approved" in value:
                return ReviewVerdict.APPROVED
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

    @classmethod
    def _extract_summary_md(cls, raw_text: str) -> str:
        pattern = r"##\s*Summary\s*\n(.*?)(?=##\s*|\Z)"
        match = re.search(pattern, raw_text, re.IGNORECASE | re.DOTALL)
        if not match:
            return ""
        return match.group(1).strip()

    @classmethod
    def _extract_first_paragraph(cls, raw_text: str) -> str | None:
        match = re.search(r"^(.+?)\n##\s", raw_text, re.DOTALL)
        if match:
            para = match.group(1).strip()
            if para.lower().startswith("verdict") or para.lower().startswith(
                "**verdict"
            ):
                return None
            return para if len(para) > 20 else None
        return None

    def _clean_response(self, content: str) -> str:
        cleaned = content.strip()
        for stop in self._STOP_TOKENS:
            idx = cleaned.find(stop)
            if idx != -1:
                cleaned = cleaned[:idx].strip()
        code_block_match = re.search(
            r"```(?:json)?\s*\n?(.*?)```",
            cleaned,
            re.DOTALL,
        )
        if code_block_match:
            cleaned = code_block_match.group(1).strip()
        return cleaned

    def _code_review_from_dict(self, data: dict[str, Any], model: str) -> CodeReview:
        items_data = data.get("items") or data.get("findings") or data.get("issues") or []
        if not isinstance(items_data, list):
            items_data = []
        items: list[ReviewItem] = []
        for i, item_dict in enumerate(items_data, 1):
            if not isinstance(item_dict, dict):
                continue
            raw_desc = item_dict.get("description", "")
            if isinstance(raw_desc, dict):
                description = ", ".join(f"{k}={v}" for k, v in raw_desc.items())
            else:
                description = str(raw_desc)
            raw_severity = str(item_dict.get("severity", "info"))
            if ItemSeverity.accepts(raw_severity):
                severity_value = raw_severity
            else:
                _, severity_value = ReviewResponseParser._infer_severity(description)
            raw_category = item_dict.get("category") or item_dict.get("type")
            if raw_category:
                category_value = str(raw_category)
            else:
                category_value = ReviewResponseParser._infer_type(description, severity_value)
            review_item = ReviewItem(
                number=i,
                severity=ItemSeverity.from_value(severity_value),
                category=IssueCategory.from_value(category_value),
                file_path=str(item_dict.get("file", "")),
                description=description,
                line=str(item_dict.get("line", "")),
                current_code=str(item_dict.get("current_code", "")),
                suggested_fix=str(item_dict.get("suggested_fix", "")),
            )
            if not review_item.file_path:
                continue
            if not review_item.current_code and not review_item.suggested_fix:
                continue
            items.append(review_item)
        return CodeReview(
            verdict=self._resolve_verdict(data.get("verdict"), items),
            reason=self._resolve_reason(data),
            summary=str(data.get("summary", "")),
            items=items,
            suggestions=[
                ReviewSuggestion(description=str(s)) if isinstance(s, str)
                else ReviewSuggestion(
                    description=str(s.get("description", "")),
                    file=str(s.get("file", "")),
                    line=str(s.get("line", "")),
                    current_code=str(s.get("current_code", "")),
                    suggested_code=str(s.get("suggested_code", "")),
                )
                for s in data.get("suggestions", [])
                if isinstance(s, (str, dict))
            ],
            praise=[
                ReviewPraise(description=str(p)) if isinstance(p, str)
                else ReviewPraise(
                    description=str(p.get("description", "")),
                    file=str(p.get("file", "")),
                )
                for p in data.get("praise", [])
                if isinstance(p, (str, dict))
            ],
            model_used=model,
        )

    @classmethod
    def _empty_review(cls, model: str, *, reason: str) -> CodeReview:
        return CodeReview(
            verdict=ReviewVerdict.COMMENTED,
            reason=reason,
            summary="",
            items=[],
            suggestions=[],
            praise=[],
            model_used=model,
        )

    @classmethod
    def _resolve_verdict(cls, 
        explicit: str | None, items: list[ReviewItem],
    ) -> ReviewVerdict:
        if explicit:
            value = explicit.strip().lower()
            if "changes" in value or "request" in value:
                return ReviewVerdict.CHANGES_REQUESTED
            if "approved" in value or value == "approve":
                return ReviewVerdict.APPROVED
            if "commented" in value:
                return ReviewVerdict.COMMENTED
            return ReviewVerdict(explicit)
        return ReviewResponseParser._determine_verdict(items)

    @classmethod
    def _resolve_reason(cls, data: dict[str, Any]) -> str:
        reason_value = data.get("reason")
        if isinstance(reason_value, str) and reason_value:
            return reason_value
        reasons_value = data.get("reasons")
        if isinstance(reasons_value, list):
            return " ".join(str(r) for r in reasons_value)
        if isinstance(reasons_value, str) and reasons_value:
            return reasons_value
        return ""

    @classmethod
    def _determine_verdict(cls, items: list[ReviewItem]) -> ReviewVerdict:
        for item in items:
            if item.severity in (ItemSeverity.CRITICAL, ItemSeverity.MAJOR):
                return ReviewVerdict.CHANGES_REQUESTED
        if items:
            return ReviewVerdict.CHANGES_REQUESTED
        return ReviewVerdict.COMMENTED

    @classmethod
    def extract_outermost_json(cls, text: str) -> str | None:
        brace_level = 0
        start = -1
        for i, ch in enumerate(text):
            if ch == "{":
                if brace_level == 0:
                    start = i
                brace_level += 1
            elif ch == "}":
                brace_level -= 1
                if brace_level == 0 and start != -1:
                    return text[start : i + 1]
        return None

    @classmethod
    def _find_items_in_dict(cls, data: dict[str, Any]) -> list[dict[str, Any]]:
        items_key = (
            data.get("items")
            or data.get("findings")
            or data.get("issues")
        )
        if isinstance(items_key, list):
            return [
                item for item in items_key
                if isinstance(item, dict)
            ]
        for value in data.values():
            if isinstance(value, dict):
                result = ReviewResponseParser._find_items_in_dict(value)
                if result:
                    return result
            if isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict):
                        result = ReviewResponseParser._find_items_in_dict(entry)
                        if result:
                            return result
        return []

    @classmethod
    def _infer_severity(cls, description: str) -> tuple[ItemSeverity, str]:
        lower = description.lower()
        if any(kw in lower for kw in ("security", "vulnerability", "injection", "leak", "hardcoded", "hard-coded")):
            return ItemSeverity.CRITICAL, ItemSeverity.CRITICAL.value
        if any(kw in lower for kw in ("crash", "data loss", "null pointer", "race condition", "deadlock")):
            return ItemSeverity.MAJOR, ItemSeverity.MAJOR.value
        if any(kw in lower for kw in ("naming", "typo", "documentation", "comment", "style")):
            return ItemSeverity.INFO, ItemSeverity.INFO.value
        return ItemSeverity.MINOR, "medium"

    @classmethod
    def _infer_type(cls, description: str, severity_str: str) -> str:
        lower = description.lower()
        if any(kw in lower for kw in ("security", "injection", "hardcoded", "leak")):
            return "security"
        if any(kw in lower for kw in ("architecture", "hexagonal", "solid", "srp", "dip", "dependency", "coupling", "single responsibility", "dependency inversion")):
            return "design"
        if "test" in lower:
            return "test"
        if any(kw in lower for kw in ("formatting", "magic", "duplication", "convention", "naming")):
            return "maintainability"
        if severity_str.lower() in ("critical", "high"):
            return "bug"
        return "quality"

    @classmethod
    def _extract_suggestions_md(cls, content: str) -> list[dict[str, str]]:
        section_match = re.search(
            r"## Suggestions\n(.*?)(?=\n## |\Z)", content, re.DOTALL
        )
        if not section_match:
            return []
        section = section_match.group(1)
        results: list[dict[str, str]] = []
        for line in section.strip().split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            parsed = ReviewResponseParser._parse_md_suggestion_line(stripped)
            if parsed is None:
                continue
            results.append(parsed)
        return results

    @classmethod
    def _extract_praise_md(cls, content: str) -> list[dict[str, str]]:
        section_match = re.search(
            r"## Praise\n(.*?)(?=\n## |\Z)", content, re.DOTALL
        )
        if not section_match:
            return []
        section = section_match.group(1)
        results: list[dict[str, str]] = []
        for line in section.strip().split("\n"):
            stripped = line.strip()
            if not stripped:
                continue
            parsed = ReviewResponseParser._parse_md_praise_line(stripped)
            if parsed is None:
                continue
            results.append(parsed)
        return results

    @classmethod
    def _parse_md_suggestion_line(cls, line: str) -> dict[str, str] | None:
        match = re.match(r"(?:\d+\.|[*-])\s+(.*)", line)
        if not match:
            return None
        rest = match.group(1).strip()
        if not rest:
            return None
        low = rest.lower()
        if "no suggestions" in low or "nothing to suggest" in low:
            return None
        file_match = re.match(r"([a-zA-Z0-9_./-]+):\s*(\d+)?\s*(.*)", rest)
        if file_match:
            return {
                "file": file_match.group(1) + ":",
                "line": file_match.group(2) or "",
                "description": file_match.group(3).strip(),
            }
        return {"file": "", "line": "", "description": rest}

    @classmethod
    def _parse_md_praise_line(cls, line: str) -> dict[str, str] | None:
        match = re.match(r"[*-]\s+(.*)", line)
        if not match:
            return None
        rest = match.group(1).strip()
        if not rest:
            return None
        low = rest.lower()
        if "no notable" in low or "nothing notable" in low or "none" == low:
            return None
        file_match = re.match(r"([a-zA-Z0-9_./-]+):\s+(.*)", rest)
        if file_match:
            return {"file": file_match.group(1), "description": file_match.group(2).strip()}
        return {"file": "", "description": rest}

    @classmethod
    def parse_items(cls, raw_text: str) -> list[dict[str, Any]]:
        """Extract a list of item dicts from a phase response.

        Each dict contains ``file``, ``severity``, ``category``,
        ``description``, ``current_code``, and ``suggested_fix`` keys.
        Returns an empty list if no items can be parsed.
        """
        cleaned = raw_text.strip()
        code_block_match = re.search(
            r"```(?:json)?\s*\n?(.*?)```",
            cleaned,
            re.DOTALL,
        )
        if code_block_match:
            cleaned = code_block_match.group(1).strip()
        try:
            data = json.loads(cleaned)
            if isinstance(data, list):
                return [
                    item for item in data
                    if isinstance(item, dict)
                ]
            if isinstance(data, dict):
                candidates = (
                    data.get("items")
                    or data.get("issues")
                    or data.get("findings")
                )
                if isinstance(candidates, list):
                    return [
                        item for item in candidates
                        if isinstance(item, dict)
                    ]
                fallback = ReviewResponseParser._find_items_in_dict(data)
                if fallback:
                    return fallback
                return []
        except (json.JSONDecodeError, ValueError):
            pass
        extracted = ReviewResponseParser.extract_outermost_json(cleaned)
        if extracted is not None:
            try:
                data = json.loads(extracted)
                if isinstance(data, list):
                    return [
                        item for item in data
                        if isinstance(item, dict)
                    ]
                if isinstance(data, dict):
                    fallback = ReviewResponseParser._find_items_in_dict(data)
                    return fallback
            except (json.JSONDecodeError, ValueError):
                pass
        logger.debug("parse_items: JSON and extraction failed, trying markdown fallback")
        markdown_items = ReviewResponseParser._parse_markdown_items(cleaned)
        if markdown_items:
            return [
                {
                    "file": item.file_path,
                    "severity": item.severity.value,
                    "category": item.category.value,
                    "description": item.description,
                    "line": item.line,
                    "current_code": item.current_code,
                    "suggested_fix": item.suggested_fix,
                }
                for item in markdown_items
            ]
        prose_items = ReviewResponseParser._parse_prose_items(cleaned)
        if prose_items:
            logger.info("parse_items: extracted %d items via prose parser", len(prose_items))
            return prose_items
        logger.warning(
            "parse_items: all parsers failed — dumping raw content (%d chars) to /tmp/parse_items_failed.txt",
            len(raw_text),
        )
        Path("/tmp/parse_items_failed.txt").write_text(raw_text)
        return []

    @classmethod
    def strip_frontmatter(cls, text: str) -> str:
        """Remove YAML frontmatter delimited by ``---`` lines."""
        cleaned = text.strip()
        if not cleaned.startswith("---"):
            return cleaned
        second = cleaned.find("---", 3)
        if second == -1:
            return cleaned
        return cleaned[second + 3:].strip()
