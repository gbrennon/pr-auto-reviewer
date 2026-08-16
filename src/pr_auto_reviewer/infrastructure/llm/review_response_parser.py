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
            data = json.loads(self._sanitize_json_literals(cleaned))
            result = self._code_review_from_dict(data, model)
            summary_empty = (not isinstance(result.summary, str) or not result.summary.strip())
            praise_empty = (not isinstance(result.praise, list) or not result.praise)
            if summary_empty or praise_empty:
                markdown_result = self._parse_markdown_fallback(content, model)
                result = self._merge_json_markdown(result, markdown_result, model)
            return result
        except (json.JSONDecodeError, ValueError):
            logger.debug("parse: JSON decode failed, trying text extraction")
        extracted = self.extract_outermost_json(cleaned)
        if extracted is not None:
            try:
                data = json.loads(self._sanitize_json_literals(extracted))
                result = self._code_review_from_dict(data, model)
                summary_empty = (not isinstance(result.summary, str) or not result.summary.strip())
                praise_empty = (not isinstance(result.praise, list) or not result.praise)
                if summary_empty or praise_empty:
                    markdown_result = self._parse_markdown_fallback(content, model)
                    result = self._merge_json_markdown(result, markdown_result, model)
                return result
            except (json.JSONDecodeError, ValueError):
                logger.debug("parse: extracted JSON decode also failed")
        markdown_result = self._parse_markdown_fallback(content, model)
        return markdown_result

    @classmethod
    def _parse_markdown_fallback(cls, content: str, model: str) -> CodeReview:
        verdict = ReviewResponseParser._extract_verdict_md(content)
        reason = ReviewResponseParser._extract_reason_md(content)
        summary = ReviewResponseParser._extract_summary_md(content)
        if not summary:
            first_para = ReviewResponseParser._extract_first_paragraph(content)
            summary = first_para if first_para else content.strip()[:500]
        items_data = ReviewResponseParser._parse_markdown_items(content)
        suggestions = ReviewResponseParser._extract_suggestions_md(content)
        praise = ReviewResponseParser._extract_praise_md(content)
        return CodeReview(
            verdict=verdict,
            reason=reason,
            summary=summary,
            items=items_data,
            suggestions=suggestions,
            praise=praise,
            model_used=model,
        )

    @classmethod
    def _merge_json_markdown(
        cls, json_result: CodeReview, markdown_result: CodeReview, model: str
    ) -> CodeReview:
        # Handle summary (string type)
        summary_is_string = isinstance(json_result.summary, str)
        summary_empty = (not summary_is_string or not json_result.summary.strip())
        summary = (
            markdown_result.summary
            if summary_empty and isinstance(markdown_result.summary, str) and markdown_result.summary.strip()
            else json_result.summary
        )
        # Handle praise (list type)
        praise_is_list = isinstance(json_result.praise, list)
        praise_empty = (not praise_is_list or not json_result.praise)
        praise = (
            markdown_result.praise
            if praise_empty and isinstance(markdown_result.praise, list) and markdown_result.praise
            else json_result.praise
        )
        # Handle suggestions (list type)
        suggestions_is_list = isinstance(json_result.suggestions, list)
        suggestions_empty = (not suggestions_is_list or not json_result.suggestions)
        suggestions = (
            markdown_result.suggestions
            if suggestions_empty and isinstance(markdown_result.suggestions, list) and markdown_result.suggestions
            else json_result.suggestions
        )
        # Handle verdict and reason (string type)
        verdict_is_string = isinstance(json_result.verdict, str)
        verdict_empty = (not verdict_is_string or not json_result.verdict.strip())
        reason_is_string = isinstance(json_result.reason, str)
        reason_empty = (not reason_is_string or not json_result.reason.strip())
        return CodeReview(
            verdict=(markdown_result.verdict if (not verdict_is_string and isinstance(markdown_result.verdict, str) and markdown_result.verdict.strip()) else json_result.verdict),
            reason=(markdown_result.reason if (not reason_is_string and isinstance(markdown_result.reason, str) and markdown_result.reason.strip()) else json_result.reason),
            summary=summary,
            items=json_result.items,
            suggestions=suggestions,
            praise=praise,
            model_used=model,
        )

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

    _STRUCTURED_ITEM = re.compile(
        r"^###\s+\[(\w+)\]\s+\[(\w+)\]\s+([^\s—:]+)(?::(\d+))?\s*—\s*(.+)$",
        re.MULTILINE,
    )

    _H4_ITEM = re.compile(
        r"^#{3,4}\s+\*?\*?\d+\.\s*\*?\*?(.+?)\*?\*?\s*$",
        re.MULTILINE,
    )

    _STRENGTHS_SECTION = re.compile(
        r"(?:###|####)\s+\*?\*?(?:Strengths?|What[’']s\s+Good|"
        r"Positives?|Praise|Good\s+Practices?)\*?\*?\s*:?\s*\n+"
        r"(.*?)(?=\n(?:#{2,4}|[A-Z].*:\s*\n)\s+|\Z)",
        re.IGNORECASE | re.DOTALL,
    )

    _RECOMMENDATION_SECTION = re.compile(
        r"(?:###|####)\s+\*?\*?(?:Areas?\s+for\s+(?:Improvement|Improvements)|"
        r"(?:Recommended\s+)?Improvements?|Recommendations?|"
        r"Suggestions?|Action\s+Items|What\s+to\s+Do\s+Next|"
        r"Suggested\s+Changes?)\*?\*?\s*:?\s*\n+"
        r"(.*?)(?=\n(?:#{2,4}|\Z))",
        re.IGNORECASE | re.DOTALL,
    )

    _ISSUE_SECTION = re.compile(
        r"(?:###|####)\s+\*?\*?(?:Issues?(?:\s+(?:Found|and\s+Improvements|Identified))?|"
        r"Problems?|Findings|Bugs?|Errors?|Concerns|"
        r"Code\s+Problems|Defects)\*?\*?\s*:?\s*\n+"
        r"(.*?)(?=\n(?:#{2,4}|\Z))",
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

    _BACKTICK_PATH = re.compile(r"`([a-zA-Z0-9_./-]+\.[a-zA-Z0-9]+)`")

    _LINE_RANGE = re.compile(
        r"(?:line|at line|:)\s*(\d+)(?:\s*(?:-|to|through)\s*(\d+))?",
        re.IGNORECASE,
    )

    _LOC_RANGE = re.compile(
        r"\b(?:[Ll](?:ine)?s?\s*)?(\d+)\s*(?:-|to|through)\s*[Ll]?\s*(\d+)\b",
        re.IGNORECASE,
    )

    _FILE_LINE = re.compile(
        r"([a-zA-Z0-9_./-]+\.[a-zA-Z0-9]+)\s*[:#]\s*(\d+)(?:\s*(?:-|to|through)\s*(\d+))?",
    )

    _SEVERITY_PATTERN = re.compile(
        r"\[(critical|major|minor|info)\]",
        re.IGNORECASE,
    )

    _CATEGORY_PATTERN = re.compile(
        r"\[(bug|security|performance|maintainability|style|quality|"
        r"architecture|solid|convention|design|documentation)\]",
        re.IGNORECASE,
    )

    _CODE_BLOCK = re.compile(
        r"```(?:python|rust|go|js|ts|java|sh|bash|yaml|json|toml|text)?\s*\n(.*?)```",
        re.DOTALL,
    )

    _FIX_HEADER = re.compile(
        r"\*\*(?:Fix|Suggested(?: Fix)?|Improved Code|Recommendation|"
        r"Should Be|Instead|Correct(?:ed)?)\*?\*?\s*:?\s*",
        re.IGNORECASE,
    )

    _CURRENT_HEADER = re.compile(
        r"\*\*(?:Current|Issue|Problem|Code)\*?\*?\s*:?\s*",
        re.IGNORECASE,
    )

    @classmethod
    def _parse_prose_items(cls, content: str) -> list[dict[str, Any]]:
        content = content.strip()
        items: list[dict[str, Any]] = []
        structured = cls._parse_structured_items(content)
        concrete_structured = cls._only_concrete(structured)
        if concrete_structured:
            return concrete_structured

        for section_match in cls._ISSUE_SECTION.finditer(content):
            section_body = section_match.group(1)
            section_items = cls._items_from_segment(section_body)
            if section_items:
                items.extend(section_items)
                return items

        flat = cls._parse_flat_prose_items(content)
        return cls._only_concrete(flat)

    @classmethod
    def _items_from_segment(cls, section_body: str) -> list[dict[str, Any]]:
        """Extract concrete findings from an issue section, one item per heading."""
        produced: list[dict[str, Any]] = []
        matches = list(cls._H4_ITEM.finditer(section_body))
        matches += list(cls._NUMBERED_ITEM.finditer(section_body))
        if not matches:
            return produced
        matches.sort(key=lambda m: m.start())
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(section_body)
            title = m.group(1).strip().rstrip("*:").strip()
            if len(title) < 5:
                continue
            item = cls._make_prose_item(title, section_body, m.end(), end)
            if item is not None:
                produced.append(item)
        return produced

    @classmethod
    def _parse_structured_items(cls, content: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for match in cls._STRUCTURED_ITEM.finditer(content):
            severity_raw, category_raw, file_path, line, description = match.groups()
            item_start = match.start()
            next_match = cls._STRUCTURED_ITEM.search(content, match.end())
            section_end = next_match.start() if next_match else len(content)
            section_body = content[item_start:section_end]
            code_blocks = cls._CODE_BLOCK.findall(section_body)
            current_code = code_blocks[0].strip() if len(code_blocks) >= 1 else ""
            suggested_fix = code_blocks[1].strip() if len(code_blocks) >= 2 else ""
            if not suggested_fix and len(code_blocks) >= 1:
                fix_match = cls._FIX_HEADER.search(section_body)
                if fix_match:
                    after_fix = section_body[fix_match.end():]
                    fix_blocks = cls._CODE_BLOCK.findall(after_fix)
                    if fix_blocks:
                        suggested_fix = fix_blocks[0].strip()
            items.append({
                "file": file_path.strip(),
                "severity": severity_raw.strip().lower(),
                "category": category_raw.strip().lower(),
                "description": description.strip(),
                "line": (line or "").strip(),
                "current_code": current_code,
                "suggested_fix": suggested_fix,
            })
        return items

    @classmethod
    def _parse_flat_prose_items(cls, content: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        matches = list(cls._H4_ITEM.finditer(content))
        if not matches:
            matches = list(cls._NUMBERED_ITEM.finditer(content))
        for i, match in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            title = match.group(1).strip().rstrip("*:").strip()
            if len(title) < 5:
                continue
            item = cls._make_prose_item(title, content, match.end(), end)
            if item is not None:
                items.append(item)
        return items

    @classmethod
    def _only_concrete(
        cls, items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Keep only items that carry a concrete current_code + suggested_fix pair."""
        concrete: list[dict[str, Any]] = []
        for item in items:
            code = str(item.get("current_code") or "").strip()
            fix = str(item.get("suggested_fix") or "").strip()
            if code and fix:
                concrete.append(item)
        return concrete

    @classmethod
    def _parse_recommendation_sections(cls, content: str) -> list[dict[str, str]]:
        """Extract non-blocking improvement/recommendation prose as suggestions."""
        suggestions: list[dict[str, str]] = []
        for match in cls._RECOMMENDATION_SECTION.finditer(content):
            section = match.group(1)
            for item_match in cls._NUMBERED_ITEM.finditer(section):
                entry = cls._prose_suggestion_entry(item_match.group(1), section)
                if entry is not None:
                    suggestions.append(entry)
            for item_match in cls._H4_ITEM.finditer(section):
                entry = cls._prose_suggestion_entry(item_match.group(1), section)
                if entry is not None:
                    suggestions.append(entry)
        return suggestions

    @classmethod
    def _prose_suggestion_entry(
        cls, title: str, section: str,
    ) -> dict[str, str] | None:
        """Turn a numbered recommendation heading into a suggestion entry."""
        slim = title.strip().rstrip("*:").strip()
        if len(slim) < 5:
            return None
        idx = section.find(title)
        if idx == -1:
            return None
        chunk = section[idx : idx + 800]
        file_path = ""
        path_match = cls._BACKTICK_PATH.search(chunk)
        if path_match:
            candidate = path_match.group(1)
            if "." in candidate:
                file_path = candidate.lstrip("/")
        line = cls._extract_line_range(chunk) or ""
        description = cls._prose_description(slim, chunk)
        return {
            "file": file_path,
            "line": line,
            "description": description,
        }

    @classmethod
    def _prose_description(cls, title: str, chunk: str) -> str:
        """Build a deep prose description from the section body."""
        code_clean = re.sub(r"```(?:[a-zA-Z0-9]+)?\s*\n.*?```", " ", chunk, flags=re.DOTALL)
        lines: list[str] = []
        for ln in code_clean.split("\n"):
            stripped = ln.strip().rstrip("*").strip()
            if not stripped:
                continue
            if stripped.startswith(("```", "###", "**")):
                continue
            no_marker = re.sub(r"^\s*(?:#+\s+|\d+\.\s*|[-*]\s+|\*\s*|\*\*)+\s*", "", stripped)
            no_marker = re.sub(r"\*\*", "", no_marker).rstrip(":").strip()
            if not no_marker or no_marker == title:
                continue
            if re.match(r"^(?:current code|suggested fix|action|file|severity|category)\b", no_marker, re.IGNORECASE):
                continue
            lines.append(no_marker)
        body = " ".join(lines).strip()
        combined = (title + ": " + body).strip() if body else title
        return combined.strip()[:600]

    @classmethod
    def parse_prose_recommendations(cls, content: str) -> list[dict[str, str]]:
        """Extract non-blocking improvement/recommendation prose as suggestions."""
        return cls._parse_recommendation_sections(content)

    @classmethod
    def parse_prose_praise(cls, content: str) -> list[dict[str, str]]:
        """Extract strengths / positive prose as praise entries."""
        praise: list[dict[str, str]] = []
        for match in cls._STRENGTHS_SECTION.finditer(content):
            section = match.group(1)
            for entry in cls._strength_entries(section):
                praise.append(entry)
        explicit = cls._extract_praise_md(content)
        for entry in explicit:
            if entry not in praise:
                praise.append(entry)
        return praise

    @classmethod
    def _strength_entries(cls, section: str) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        for item_match in cls._NUMBERED_ITEM.finditer(section):
            entry = cls._prose_praise_entry(item_match.group(1), section)
            if entry is not None:
                entries.append(entry)
        for item_match in cls._H4_ITEM.finditer(section):
            entry = cls._prose_praise_entry(item_match.group(1), section)
            if entry is not None:
                entries.append(entry)
        return entries

    @classmethod
    def _prose_praise_entry(
        cls, title: str, section: str,
    ) -> dict[str, str] | None:
        slim = title.strip().rstrip("*:").strip()
        if len(slim) < 5:
            return None
        idx = section.find(title)
        if idx == -1:
            return None
        chunk = section[idx : idx + 600]
        file_path = ""
        path_match = cls._BACKTICK_PATH.search(chunk)
        if path_match:
            candidate = path_match.group(1)
            if "." in candidate:
                file_path = candidate.lstrip("/")
        description = cls._prose_description(slim, chunk)
        return {
            "file": file_path,
            "description": description,
        }

    @classmethod
    def _extract_line_range(cls, context: str) -> str:
        """Return ``"start-end"`` (or ``"start"``) from line references."""
        for pattern in (ReviewResponseParser._LOC_RANGE,
                        ReviewResponseParser._FILE_LINE,
                        ReviewResponseParser._LINE_RANGE):
            m = re.search(pattern, context)
            if m:
                start = m.group(1)
                end = m.group(2) if m.lastindex and m.lastindex >= 2 and m.group(2) else ""
                return f"{start}-{end}" if end else start
        return ""

    @classmethod
    def _make_prose_item(
        cls, title: str, section_body: str, match_start: int,
        segment_end: int | None = None,
    ) -> dict[str, Any] | None:
        context_end = segment_end if segment_end is not None else min(match_start + 1200, len(section_body))
        context = section_body[match_start:context_end]
        code_blocks = cls._CODE_BLOCK.findall(context)
        current_code = code_blocks[0].strip() if len(code_blocks) >= 1 else ""
        suggested_fix = ""
        if len(code_blocks) >= 2:
            suggested_fix = code_blocks[1].strip()
        elif len(code_blocks) >= 1:
            fix_match = cls._FIX_HEADER.search(context)
            if fix_match:
                after_fix = context[fix_match.end():]
                fix_blocks = cls._CODE_BLOCK.findall(after_fix)
                if fix_blocks:
                    suggested_fix = fix_blocks[0].strip()
        if not current_code:
            current_match = cls._CURRENT_HEADER.search(context)
            if current_match:
                after_current = context[current_match.end():]
                cur_blocks = cls._CODE_BLOCK.findall(after_current)
                if cur_blocks:
                    current_code = cur_blocks[0].strip()
        if not current_code or not suggested_fix:
            return None
        file_path = ""
        path_match = cls._BACKTICK_PATH.search(context)
        if path_match:
            candidate = path_match.group(1)
            if "." in candidate and not candidate.startswith("`"):
                file_path = candidate
        if not file_path:
            path_in_title = cls._BACKTICK_PATH.search(title)
            if path_in_title:
                candidate = path_in_title.group(1)
                if "." in candidate:
                    file_path = candidate
        if not file_path:
            file_line = cls._FILE_LINE.search(context)
            if file_line:
                file_path = file_line.group(1).lstrip("/")
        line = cls._extract_line_range(context)
        severity = "minor"
        sev_match = cls._SEVERITY_PATTERN.search(title)
        if not sev_match:
            sev_match = cls._SEVERITY_PATTERN.search(context[:200])
        if sev_match:
            severity = sev_match.group(1).lower()
        category = "maintainability"
        cat_match = cls._CATEGORY_PATTERN.search(title)
        if not cat_match:
            cat_match = cls._CATEGORY_PATTERN.search(context[:200])
        if cat_match:
            category = cat_match.group(1).lower()
        description = cls._prose_description(title.strip(), context)
        return {
            "file": file_path,
            "severity": severity,
            "category": category,
            "description": description,
            "line": line,
            "current_code": current_code,
            "suggested_fix": suggested_fix,
        }

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
    def _extract_reason_md(cls, raw_text: str) -> str:
        patterns = [
            r"\*\*Reason:\s*\*\*(.+)",
            r"Reason[:\s]+(.+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, raw_text, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                if value:
                    return value
        return ""

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
            if not review_item.file_path and not review_item.description:
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
            reason=reason or (
                "Application could not extract a structured verdict "
                "from the LLM output."
            ),
            summary=(
                "No structured review data was obtained from the LLM output. "
                "This is a pipeline failure signal, not a clean review."
            ),
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

    @staticmethod
    def _normalize_item_dict(item: dict[str, Any]) -> dict[str, Any]:
        """Map LLM JSON item fields onto the canonical parser schema."""
        severity_raw = str(item.get("severity") or "minor").lower().strip()
        severity_map = {
            "high": "major", "medium": "minor", "low": "minor",
            "critical": "critical", "major": "major", "minor": "minor",
            "info": "info",
        }
        category_default = "maintainability"
        category_raw = str(
            item.get("category") or item.get("type") or ""
        ).lower().strip()
        category = {
            "bug": "bug", "security": "security",
            "performance": "performance", "maintainability": "maintainability",
            "style": "style", "quality": "quality",
            "architecture": "architecture", "solid": "design",
            "design": "design", "convention": "maintainability",
        }.get(category_raw, category_default)
        description = str(
            item.get("description")
            or item.get("issue")
            or item.get("title")
            or item.get("message")
            or ""
        )
        current_code = str(item.get("current_code") or item.get("code") or "")
        suggested_fix = str(item.get("suggested_fix") or item.get("fix") or "")
        category_raw_lower = category_raw
        if suggested_fix == "" and description:
            suggested_fix = (
                f"Resolve the reported {category_raw_lower or 'issue'}: {description}"
            )
        return {
            "file": str(item.get("file") or item.get("file_path") or ""),
            "line": str(item.get("line") or ""),
            "severity": severity_map.get(severity_raw, severity_raw),
            "category": category,
            "description": description,
            "current_code": current_code,
            "suggested_fix": suggested_fix,
        }

    @classmethod
    def parse_item_observations(cls, raw_text: str) -> list[dict[str, str]]:
        """Extract fix-less LLM item dicts as non-blocking suggestions."""
        normalized = cls._extract_item_dicts(raw_text)
        concrete_keys = {
            (str(i.get("file") or ""), str(i.get("description") or ""))
            for i in cls._only_concrete(normalized)
        }
        observations: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for i in normalized:
            if cls._is_concrete(i):
                continue
            key = (str(i.get("file") or ""), str(i.get("description") or ""))
            if key in concrete_keys or key in seen:
                continue
            seen.add(key)
            observations.append({
                "file": str(i.get("file") or ""),
                "line": str(i.get("line") or ""),
                "description": str(
                    i.get("description") or "Review the identified concern."
                ),
            })
        return observations

    @classmethod
    def _extract_item_dicts(cls, raw_text: str) -> list[dict[str, Any]]:
        """Extract all normalized item dicts from JSON content (concrete or not)."""
        cleaned = raw_text.strip()
        code_block_match = re.search(
            r"```(?:json)?\s*\n?(.*?)```", cleaned, re.DOTALL
        )
        if code_block_match:
            try:
                json.loads(code_block_match.group(1))
                cleaned = code_block_match.group(1)
            except (json.JSONDecodeError, ValueError):
                pass
        for source in (cleaned,):
            try:
                data = json.loads(ReviewResponseParser._sanitize_json_literals(source))
            except (json.JSONDecodeError, ValueError):
                continue
            if isinstance(data, dict):
                candidates = (
                    data.get("items") or data.get("issues") or data.get("findings")
                )
                if isinstance(candidates, list):
                    return [
                        ReviewResponseParser._normalize_item_dict(item)
                        for item in candidates
                        if isinstance(item, dict)
                    ]
                fallback = ReviewResponseParser._find_items_in_dict(data)
                if fallback:
                    return [
                        ReviewResponseParser._normalize_item_dict(item)
                        for item in fallback
                    ]
            elif isinstance(data, list):
                return [
                    ReviewResponseParser._normalize_item_dict(item)
                    for item in data
                    if isinstance(item, dict)
                ]
        return []

    @staticmethod
    def _is_concrete(item: dict[str, Any]) -> bool:
        code = str(item.get("current_code") or "").strip()
        fix = str(item.get("suggested_fix") or "").strip()
        return bool(code) and bool(fix)

    @staticmethod
    def _sanitize_json_literals(text: str) -> str:
        """Escape raw control characters inside JSON string literals."""
        out: list[str] = []
        in_string = False
        escaped = False
        for ch in text:
            if escaped:
                out.append(ch)
                escaped = False
                continue
            if ch == "\\":
                out.append(ch)
                escaped = True
                continue
            if ch == '"':
                out.append(ch)
                in_string = not in_string
                continue
            if in_string and ord(ch) < 0x20:
                mapping = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}
                out.append(mapping.get(ch, f"\\u{ord(ch):04x}"))
                continue
            out.append(ch)
        return "".join(out)

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
            extracted = code_block_match.group(1).strip()
            try:
                json.loads(extracted)
                cleaned = extracted
            except (json.JSONDecodeError, ValueError):
                pass
        try:
            data = json.loads(ReviewResponseParser._sanitize_json_literals(cleaned))
            if isinstance(data, list):
                return cls._only_concrete([
                    ReviewResponseParser._normalize_item_dict(item)
                    for item in data
                    if isinstance(item, dict)
                ])
            if isinstance(data, dict):
                candidates = (
                    data.get("items")
                    or data.get("issues")
                    or data.get("findings")
                )
                if isinstance(candidates, list):
                    return cls._only_concrete([
                        ReviewResponseParser._normalize_item_dict(item)
                        for item in candidates
                        if isinstance(item, dict)
                    ])
                fallback = ReviewResponseParser._find_items_in_dict(data)
                if fallback:
                    return cls._only_concrete([
                        ReviewResponseParser._normalize_item_dict(item)
                        for item in fallback
                    ])
                return []
        except (json.JSONDecodeError, ValueError):
            pass
        extracted = ReviewResponseParser.extract_outermost_json(cleaned)
        if extracted is not None:
            try:
                data = json.loads(ReviewResponseParser._sanitize_json_literals(extracted))
                if isinstance(data, list):
                    return cls._only_concrete([
                        ReviewResponseParser._normalize_item_dict(item)
                        for item in data
                        if isinstance(item, dict)
                    ])
                if isinstance(data, dict):
                    fallback = ReviewResponseParser._find_items_in_dict(data)
                    return cls._only_concrete([
                        ReviewResponseParser._normalize_item_dict(item)
                        for item in fallback
                    ])
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
