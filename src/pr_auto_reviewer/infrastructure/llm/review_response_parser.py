"""Parse LLM review responses into domain objects."""

from __future__ import annotations

import json
import logging
import re
import uuid as _uuid
from pathlib import Path
from typing import Any

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.exceptions.review_verdict_error import (
    ReviewVerdictError,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict

logger = logging.getLogger(__name__)


class ReviewResponseParser:
    """Parse the raw LLM text into a CodeReview domain object."""

    _STOP_TOKENS = ("<|im_end|>", "<｜end▁of▁thinking｜>")
    @classmethod
    def _new_suggestion_id(cls) -> str:
        """Return a six-character lowercase hexadecimal suggestion ID."""
        return _uuid.uuid4().hex[:6]

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

    _ROOT_CAUSE = re.compile(r"(?im)^\s*\**\s*root cause\s*\**\s*:\s*(.+)$")
    _REPRODUCTION = re.compile(r"(?im)^\s*\**\s*reproduction\s*\**\s*:\s*(.+)$")
    _ACCEPTANCE = re.compile(
        r"(?im)^\s*\**\s*acceptance criteria\s*\**\s*:\s*(.+)$"
    )
    _DETECTION = re.compile(
        r"(?im)^\s*\**\s*detection method\s*\**\s*:\s*(.+)$"
    )

    def __init__(self) -> None:
        pass

    @staticmethod
    def _first_group(pattern: "re.Pattern[str]", text: str) -> str:
        """Return the first capture group of *pattern* in *text*, else ``""``."""
        match = pattern.search(text)
        return match.group(1).strip() if match else ""


    def _parse_markdown_fallback(self, content: str, model: str) -> CodeReview:
        required_sections = (
            r"(?im)^##\s+(?:Items|Issues|Findings)\b",
            r"(?im)^##\s+Suggestions\b",
            r"(?im)^##\s+Praise\b",
        )
        if any(re.search(section, content) is None for section in required_sections):
            raise ReviewVerdictError(
                "Markdown review output must contain explicit items, suggestions, "
                "and praise sections."
            )
        verdict = self.extract_verdict_md(content)
        reason = self._extract_reason_md(content).strip()
        summary = self._extract_summary_md(content).strip()
        if not reason or not summary:
            raise ReviewVerdictError(
                "Markdown review output must contain a non-empty reason and summary."
            )
        items_data = self._parse_markdown_items(content)
        suggestions = self._review_items_from_collection(
            self._extract_suggestions_md(content),
            "suggestions",
        )
        praise = self._review_items_from_collection(
            self._extract_praise_md(content),
            "praise",
        )
        return CodeReview(
            verdict=verdict,
            reason=reason,
            summary=summary,
            items=items_data,
            suggestions=suggestions,
            praise=praise,
            model_used=model,
        )

    def _parse_markdown_items(self, content: str) -> list[ReviewItem]:
        pattern = re.compile(
            r"^-\s*\[(\w+)\]\s+(\w+)\s+\(([^)]+)\)\s+(.+)$",
            re.MULTILINE,
        )
        items: list[ReviewItem] = []
        for match in pattern.finditer(content):
            severity_raw, category_raw, file_path, description = match.groups()
            normalized = self.normalize_item_dict({
                "file": file_path.strip(),
                "severity": severity_raw,
                "category": category_raw,
                "description": description.strip(),
            })
            items.append(
                ReviewItem(
                    severity=normalized["severity"],
                    category=normalized["category"],
                    file_path=normalized["file"],
                    description=normalized["description"],
                    line=normalized["line"],
                    current_code=normalized["current_code"],
                    suggested_fix=normalized["suggested_fix"],
                    id=format(_uuid.uuid7().int, "04x")[:4],
                )
            )
        return items

    def _parse_prose_items(self, content: str) -> list[dict[str, Any]]:
        content = content.strip()
        items: list[dict[str, Any]] = []
        structured = self._parse_structured_items(content)
        concrete_structured = self._only_concrete(structured)
        if concrete_structured:
            return concrete_structured

        for section_match in self._ISSUE_SECTION.finditer(content):
            section_body = section_match.group(1)
            section_items = self._items_from_segment(section_body)
            if section_items:
                items.extend(section_items)
                return items

        flat = self._parse_flat_prose_items(content)
        return self._only_concrete(flat)

    def _items_from_segment(self, section_body: str) -> list[dict[str, Any]]:
        """Extract concrete findings from an issue section, one item per heading."""
        produced: list[dict[str, Any]] = []
        matches = list(self._H4_ITEM.finditer(section_body))
        matches += list(self._NUMBERED_ITEM.finditer(section_body))
        if not matches:
            return produced
        matches.sort(key=lambda m: m.start())
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(section_body)
            title = m.group(1).strip().rstrip("*:").strip()
            if len(title) < 5:
                continue
            item = self._make_prose_item(title, section_body, m.end(), end)
            if item is not None:
                produced.append(item)
        return produced

    def _parse_structured_items(self, content: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for match in self._STRUCTURED_ITEM.finditer(content):
            severity_raw, category_raw, file_path, line, description = match.groups()
            item_start = match.start()
            next_match = self._STRUCTURED_ITEM.search(content, match.end())
            section_end = next_match.start() if next_match else len(content)
            section_body = content[item_start:section_end]
            code_blocks = self._CODE_BLOCK.findall(section_body)
            current_code = code_blocks[0].strip() if len(code_blocks) >= 1 else ""
            suggested_fix = code_blocks[1].strip() if len(code_blocks) >= 2 else ""
            if not suggested_fix and len(code_blocks) >= 1:
                fix_match = self._FIX_HEADER.search(section_body)
                if fix_match:
                    after_fix = section_body[fix_match.end():]
                    fix_blocks = self._CODE_BLOCK.findall(after_fix)
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
                "root_cause": self._first_group(self._ROOT_CAUSE, section_body),
                "reproduction": self._first_group(
                    self._REPRODUCTION, section_body
                ),
                "acceptance_criteria": self._first_group(
                    self._ACCEPTANCE, section_body
                ),
                "detection_method": self._first_group(
                    self._DETECTION, section_body
                ),
            })
        return items

    def _parse_flat_prose_items(self, content: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        matches = list(self._H4_ITEM.finditer(content))
        if not matches:
            matches = list(self._NUMBERED_ITEM.finditer(content))
        for i, match in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
            title = match.group(1).strip().rstrip("*:").strip()
            if len(title) < 5:
                continue
            item = self._make_prose_item(title, content, match.end(), end)
            if item is not None:
                items.append(item)
        return items

    def _only_concrete(
        self, items: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Keep only items that carry a concrete current_code + suggested_fix pair."""
        concrete: list[dict[str, Any]] = []
        for item in items:
            code = str(item.get("current_code") or "").strip()
            fix = str(item.get("suggested_fix") or "").strip()
            if code and fix:
                concrete.append(item)
        return concrete

    def _parse_recommendation_sections(self, content: str) -> list[dict[str, str]]:
        """Extract non-blocking improvement/recommendation prose as suggestions."""
        suggestions: list[dict[str, str]] = []
        for match in self._RECOMMENDATION_SECTION.finditer(content):
            section = match.group(1)
            for item_match in self._NUMBERED_ITEM.finditer(section):
                entry = self._prose_suggestion_entry(item_match.group(1), section)
                if entry is not None:
                    suggestions.append(entry)
            for item_match in self._H4_ITEM.finditer(section):
                entry = self._prose_suggestion_entry(item_match.group(1), section)
                if entry is not None:
                    suggestions.append(entry)
        return suggestions

    def _prose_suggestion_entry(
        self, title: str, section: str,
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
        path_match = self._BACKTICK_PATH.search(chunk)
        if path_match:
            candidate = path_match.group(1)
            if "." in candidate:
                file_path = candidate.lstrip("/")
        line = self._extract_line_range(chunk) or ""
        description = self._prose_description(slim, chunk)
        current_code, suggested_fix = self._extract_code_blocks(chunk)
        return {
            "file": file_path,
            "line": line,
            "description": description,
            "current_code": current_code,
            "suggested_fix": suggested_fix,
        }

    def _extract_code_blocks(self, chunk: str) -> tuple[str, str]:
        """Extract current_code and suggested_fix from code blocks in chunk."""
        current_code = ""
        suggested_fix = ""
        # Find all code blocks
        code_blocks = re.findall(r"```(?:[a-zA-Z0-9]+)?\s*\n(.*?)```", chunk, re.DOTALL)
        for i, block in enumerate(code_blocks):
            block = block.strip()
            # Look for markers indicating current vs suggested
            lower = block.lower()
            if any(marker in lower for marker in ("current", "before", "old", "original")):
                current_code = block
            elif any(marker in lower for marker in ("suggested", "after", "new", "fix", "fixed")):
                suggested_fix = block
            elif i == 0 and not current_code:
                # First block without markers - assume current
                current_code = block
            elif i == 1 and not suggested_fix:
                # Second block without markers - assume suggested
                suggested_fix = block
        # Fallback: if we have current but no suggested, use description or current as suggested
        if current_code and not suggested_fix:
            # Try to find a second code block or use first as both
            if len(code_blocks) > 1:
                suggested_fix = code_blocks[1].strip()
            else:
                # No second block - current is the fix (it's a one-line change)
                suggested_fix = current_code
        return current_code, suggested_fix

    def _prose_description(self, title: str, chunk: str) -> str:
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

    def parse_prose_recommendations(self, content: str) -> list[dict[str, str]]:
        """Extract non-blocking improvement/recommendation prose as suggestions."""
        return self._parse_recommendation_sections(content)

    def parse_prose_praise(self, content: str) -> list[dict[str, str]]:
        """Extract strengths / positive prose as praise entries."""
        praise: list[dict[str, str]] = []
        for match in self._STRENGTHS_SECTION.finditer(content):
            section = match.group(1)
            praise.extend(self._strength_entries(section))
        explicit = self._extract_praise_md(content)
        for entry in explicit:
            if entry not in praise:
                praise.append(entry)
        return praise

    def _strength_entries(self, section: str) -> list[dict[str, str]]:
        entries: list[dict[str, str]] = []
        for item_match in self._NUMBERED_ITEM.finditer(section):
            entry = self._prose_praise_entry(item_match.group(1), section)
            if entry is not None:
                entries.append(entry)
        for item_match in self._H4_ITEM.finditer(section):
            entry = self._prose_praise_entry(item_match.group(1), section)
            if entry is not None:
                entries.append(entry)
        return entries

    def _prose_praise_entry(
        self, title: str, section: str,
    ) -> dict[str, str] | None:
        slim = title.strip().rstrip("*:").strip()
        if len(slim) < 5:
            return None
        idx = section.find(title)
        if idx == -1:
            return None
        chunk = section[idx : idx + 600]
        file_path = ""
        path_match = self._BACKTICK_PATH.search(chunk)
        if path_match:
            candidate = path_match.group(1)
            if "." in candidate:
                file_path = candidate.lstrip("/")
        description = self._prose_description(slim, chunk)
        return {
            "file": file_path,
            "description": description,
        }

    def _extract_line_range(self, context: str) -> str:
        """Return ``"start-end"`` (or ``"start"``) from line references."""
        for pattern in (self._LOC_RANGE,
                        self._FILE_LINE,
                        self._LINE_RANGE):
            m = re.search(pattern, context)
            if m:
                if pattern is self._FILE_LINE:
                    start = m.group(2)
                    end_offset = 3
                else:
                    start = m.group(1)
                    end_offset = 2
                end = m.group(end_offset) if m.lastindex and m.lastindex >= end_offset and m.group(end_offset) else ""
                return f"{start}-{end}" if end else start
        return ""

    def _make_prose_item(
        self, title: str, section_body: str, match_start: int,
        segment_end: int | None = None,
    ) -> dict[str, Any] | None:
        context_end = segment_end if segment_end is not None else min(match_start + 1200, len(section_body))
        context = section_body[match_start:context_end]
        code_blocks = self._CODE_BLOCK.findall(context)
        current_code = code_blocks[0].strip() if len(code_blocks) >= 1 else ""
        suggested_fix = ""
        if len(code_blocks) >= 2:
            suggested_fix = code_blocks[1].strip()
        elif len(code_blocks) >= 1:
            fix_match = self._FIX_HEADER.search(context)
            if fix_match:
                after_fix = context[fix_match.end():]
                fix_blocks = self._CODE_BLOCK.findall(after_fix)
                if fix_blocks:
                    suggested_fix = fix_blocks[0].strip()
        if not current_code:
            current_match = self._CURRENT_HEADER.search(context)
            if current_match:
                after_current = context[current_match.end():]
                cur_blocks = self._CODE_BLOCK.findall(after_current)
                if cur_blocks:
                    current_code = cur_blocks[0].strip()
        if not current_code or not suggested_fix:
            return None
        file_path = ""
        path_match = self._BACKTICK_PATH.search(context)
        if path_match:
            candidate = path_match.group(1)
            if "." in candidate and not candidate.startswith("`"):
                file_path = candidate
        if not file_path:
            path_in_title = self._BACKTICK_PATH.search(title)
            if path_in_title:
                candidate = path_in_title.group(1)
                if "." in candidate:
                    file_path = candidate
        if not file_path:
            file_line = self._FILE_LINE.search(context)
            if file_line:
                file_path = file_line.group(1).lstrip("/")
        line = self._extract_line_range(context)
        severity = "minor"
        sev_match = self._SEVERITY_PATTERN.search(title)
        if not sev_match:
            sev_match = self._SEVERITY_PATTERN.search(context[:200])
        if sev_match:
            severity = sev_match.group(1).lower()
        category = "maintainability"
        cat_match = self._CATEGORY_PATTERN.search(title)
        if not cat_match:
            cat_match = self._CATEGORY_PATTERN.search(context[:200])
        if cat_match:
            category = cat_match.group(1).lower()
        description = self._prose_description(title.strip(), context)
        return {
            "file": file_path,
            "severity": severity,
            "category": category,
            "description": description,
            "line": line,
            "current_code": current_code,
            "suggested_fix": suggested_fix,
        }

    def extract_verdict_md(self, raw_text: str) -> ReviewVerdict:
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
        match = re.search(r"Verdict:\s*(.+)", raw_text, re.IGNORECASE)
        if match:
            value = match.group(1).strip().lower()
            if "changes" in value or "request" in value:
                return ReviewVerdict.CHANGES_REQUESTED
            if "approved" in value or value == "approve":
                return ReviewVerdict.APPROVED
        raise ReviewVerdictError(
            "Could not extract an APPROVED or CHANGES_REQUESTED verdict "
            "from the LLM markdown output; refusing to default to COMMENTED."
        )

    def _extract_summary_md(self, raw_text: str) -> str:
        pattern = r"##\s*Summary\s*\n(.*?)(?=##\s*|\Z)"
        match = re.search(pattern, raw_text, re.IGNORECASE | re.DOTALL)
        if not match:
            return ""
        return match.group(1).strip()

    def _extract_reason_md(self, raw_text: str) -> str:
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

    def _extract_first_paragraph(self, raw_text: str) -> str | None:
        match = re.search(r"^(.+?)\n##\s", raw_text, re.DOTALL)
        if match:
            para = match.group(1).strip()
            if para.lower().startswith("verdict") or para.lower().startswith(
                "**verdict"
            ):
                return None
            return para if len(para) > 20 else None
        return None


    def _resolve_verdict(
        self, explicit: object, items: list[ReviewItem],
    ) -> ReviewVerdict:
        verdict = ReviewVerdict.coerce(explicit)
        if verdict is ReviewVerdict.APPROVED:
            return ReviewVerdict.APPROVED
        if verdict is ReviewVerdict.CHANGES_REQUESTED:
            return ReviewVerdict.CHANGES_REQUESTED
        raise ReviewVerdictError(
            f"LLM returned an unrecognized verdict {explicit!r}; "
            "an explicit APPROVED or CHANGES_REQUESTED verdict is required."
        )

    def _resolve_reason(self, data: dict[str, Any]) -> str:
        reason_value = data.get("reason")
        if isinstance(reason_value, str) and reason_value.strip():
            return reason_value.strip()
        raise ReviewVerdictError(
            "Review output must contain a non-empty explicit reason."
        )


    @staticmethod
    def extract_outermost_json(text: str) -> str | None:
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

    def _find_items_in_dict(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        supplied = [key for key in ("items", "findings", "issues") if key in data]
        if supplied:
            items_key = self._provided_collection(
                data,
                ("items", "findings", "issues"),
                "findings",
            )
            return [
                item for item in items_key
                if isinstance(item, dict)
            ]
        for value in data.values():
            if isinstance(value, dict):
                result = self._find_items_in_dict(value)
                if result:
                    return result
            if isinstance(value, list):
                for entry in value:
                    if isinstance(entry, dict):
                        result = self._find_items_in_dict(entry)
                        if result:
                            return result
        return []

    def _infer_severity(self, description: str) -> tuple[ItemSeverity, str]:
        lower = description.lower()
        if any(kw in lower for kw in ("security", "vulnerability", "injection", "leak", "hardcoded", "hard-coded")):
            return ItemSeverity.CRITICAL, ItemSeverity.CRITICAL.value
        if any(kw in lower for kw in ("crash", "data loss", "null pointer", "race condition", "deadlock")):
            return ItemSeverity.MAJOR, ItemSeverity.MAJOR.value
        if any(kw in lower for kw in ("naming", "typo", "documentation", "comment", "style")):
            return ItemSeverity.INFO, ItemSeverity.INFO.value
        return ItemSeverity.MINOR, "medium"

    def _infer_type(self, description: str, severity_str: str) -> str:
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

    def _extract_suggestions_md(self, content: str) -> list[dict[str, str]]:
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
            parsed = self._parse_md_suggestion_line(stripped)
            if parsed is None:
                continue
            results.append(parsed)
        return results

    def _extract_praise_md(self, content: str) -> list[dict[str, str]]:
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
            parsed = self._parse_md_praise_line(stripped)
            if parsed is None:
                continue
            results.append(parsed)
        return results

    def _parse_md_suggestion_line(self, line: str) -> dict[str, str] | None:
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

    def _parse_md_praise_line(self, line: str) -> dict[str, str] | None:
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

    def parse_item_observations(self, raw_text: str) -> list[dict[str, str]]:
        """Extract fix-less LLM item dicts as non-blocking suggestions."""
        normalized = self._extract_item_dicts(raw_text)
        concrete_keys = {
            (str(i.get("file") or ""), str(i.get("description") or ""))
            for i in self._only_concrete(normalized)
        }
        observations: list[dict[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for i in normalized:
            if self._is_concrete(i):
                continue
            key = (str(i.get("file") or ""), str(i.get("description") or ""))
            if key in concrete_keys or key in seen:
                continue
            seen.add(key)
            description = str(i.get("description") or "").strip()
            if not description:
                continue
            observations.append({
                "file": str(i.get("file") or ""),
                "line": str(i.get("line") or ""),
                "description": description,
            })
        return observations

    def _extract_item_dicts(self, raw_text: str) -> list[dict[str, Any]]:
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
                data = json.loads(self.sanitize_json_literals(source))
                if isinstance(data, dict):
                    direct_keys = [
                        key for key in ("items", "issues", "findings")
                        if key in data
                    ]
                    if direct_keys:
                        candidates = self._provided_collection(
                            data,
                            ("items", "issues", "findings"),
                            "findings",
                        )
                        return [
                            self.normalize_item_dict(item)
                            for item in candidates
                            if isinstance(item, dict)
                        ]
                    fallback = self._find_items_in_dict(data)
                    if fallback:
                        return [
                            self.normalize_item_dict(item)
                            for item in fallback
                        ]
                elif isinstance(data, list):
                    return [
                        self.normalize_item_dict(item)
                        for item in data
                        if isinstance(item, dict)
                    ]
            except (json.JSONDecodeError, ValueError):
                continue
        return []

    def parse_items(self, raw_text: str) -> list[dict[str, Any]]:
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
            data = json.loads(self.sanitize_json_literals(cleaned))
            if isinstance(data, list):
                return self._only_concrete([
                    self.normalize_item_dict(item)
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
                    return self._only_concrete([
                        self.normalize_item_dict(item)
                        for item in candidates
                        if isinstance(item, dict)
                    ])
                fallback = self._find_items_in_dict(data)
                if fallback:
                    return self._only_concrete([
                        self.normalize_item_dict(item)
                        for item in fallback
                    ])
                return []
        except (json.JSONDecodeError, ValueError):
            pass
        extracted = self.extract_outermost_json(cleaned)
        if extracted is not None:
            try:
                data = json.loads(self.sanitize_json_literals(extracted))
                if isinstance(data, list):
                    return self._only_concrete([
                        self.normalize_item_dict(item)
                        for item in data
                        if isinstance(item, dict)
                    ])
                if isinstance(data, dict):
                    fallback = self._find_items_in_dict(data)
                    return self._only_concrete([
                        self.normalize_item_dict(item)
                        for item in fallback
                    ])
            except (json.JSONDecodeError, ValueError):
                pass
        logger.debug("parse_items: JSON and extraction failed, trying markdown fallback")
        markdown_items = self._parse_markdown_items(cleaned)
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
        prose_items = self._parse_prose_items(cleaned)
        if prose_items:
            logger.info("parse_items: extracted %d items via prose parser", len(prose_items))
            return prose_items
        logger.warning(
            "parse_items: all parsers failed — dumping raw content (%d chars) to /tmp/parse_items_failed.txt",
            len(raw_text),
        )
        Path("/tmp/parse_items_failed.txt").write_text(raw_text)
        return []

    @staticmethod
    def strip_frontmatter(text: str) -> str:
        """Remove YAML frontmatter delimited by ``---`` lines."""
        cleaned = text.strip()
        if not cleaned.startswith("---"):
            return cleaned
        second = cleaned.find("---", 3)
        if second == -1:
            return cleaned
        return cleaned[second + 3:].strip()

    @staticmethod
    def _provided_collection(
        data: dict[str, Any], keys: tuple[str, ...], label: str,
    ) -> list[Any]:
        supplied = [key for key in keys if key in data]
        if len(supplied) != 1:
            raise ReviewVerdictError(
                f"Review output must supply exactly one {label} collection."
            )
        value = data[supplied[0]]
        if not isinstance(value, list):
            raise ReviewVerdictError(f"Review {label} collection must be a list.")
        return value

    def _review_items_from_collection(
        self, raw: list[Any], label: str,
    ) -> list[ReviewItem]:
        result: list[ReviewItem] = []
        for entry in raw:
            if isinstance(entry, str):
                description = entry.strip()
                values: dict[str, Any] = {}
            elif isinstance(entry, dict):
                description_value = entry.get("description")
                if not isinstance(description_value, str):
                    raise ReviewVerdictError(
                        f"Each {label} entry must supply a string description."
                    )
                description = description_value.strip()
                values = entry
            else:
                raise ReviewVerdictError(
                    f"Each {label} entry must be a string or object."
                )
            if not description:
                raise ReviewVerdictError(
                    f"Each {label} entry must have a non-empty description."
                )
            suggested_fix = values.get(
                "suggested_fix", values.get("suggested_code", "")
            )
            if not isinstance(suggested_fix, str):
                raise ReviewVerdictError(
                    f"Each {label} suggested_fix must be a string."
                )
            result.append(
                ReviewItem(
                    severity=ItemSeverity.INFO,
                    category=IssueCategory.GENERAL,
                    file_path=str(values.get("file") or values.get("file_path") or ""),
                    description=description,
                    line=str(values.get("line") or ""),
                    id=self._new_suggestion_id() if label == "suggestions" else "",
                    current_code=str(
                        values.get("current_code")
                        or values.get("current")
                        or ""
                    ),
                    suggested_fix=suggested_fix,
                )
            )
        return result

    @staticmethod
    def normalize_item_dict(item: dict[str, Any]) -> dict[str, Any]:
        """Map LLM JSON item fields onto the canonical parser schema."""
        if not isinstance(item, dict):
            raise ReviewVerdictError("Each review item must be an object.")

        severity_value = item.get("severity")
        if not isinstance(severity_value, str):
            raise ReviewVerdictError("Each review item must supply severity.")
        severity_aliases = {
            "high": "major",
            "medium": "minor",
            "low": "minor",
            "critical": "critical",
            "major": "major",
            "minor": "minor",
            "info": "info",
        }
        severity = severity_aliases.get(severity_value.strip().lower())
        if severity is None:
            raise ReviewVerdictError(
                f"Review item has invalid severity {severity_value!r}."
            )

        category_value = (
            item.get("category") if "category" in item else item.get("type")
        )
        if not isinstance(category_value, str):
            raise ReviewVerdictError("Each review item must supply category.")
        category_aliases = {
            category.value: category.value for category in IssueCategory
        }
        category_aliases.update({
            "architecture": "design",
            "solid": "design",
            "doc": "docs",
            "tests": "test",
            "correctness": "bug",
            "safety": "security",
            "best-practices": "quality",
            "error-handling": "bug",
            "concurrency": "bug",
        })
        category = category_aliases.get(category_value.strip().lower())
        if category is None:
            raise ReviewVerdictError(
                f"Review item has invalid category {category_value!r}."
            )

        description_key = next(
            (key for key in ("description", "issue", "title", "message") if key in item),
            None,
        )
        description_value = item.get(description_key) if description_key else None
        if not isinstance(description_value, str) or not description_value.strip():
            raise ReviewVerdictError(
                "Each review item must supply a non-empty description."
            )

        current_code = item.get("current_code", item.get("code", ""))
        suggested_fix = item.get("suggested_fix", item.get("fix", ""))
        if not isinstance(current_code, str) or not isinstance(suggested_fix, str):
            raise ReviewVerdictError(
                "Review item code fields must be strings when supplied."
            )
        return {
            "file": str(item.get("file") or item.get("file_path") or ""),
            "line": str(item.get("line") or ""),
            "severity": severity,
            "category": category,
            "description": description_value.strip(),
            "current_code": current_code,
            "suggested_fix": suggested_fix,
            "root_cause": str(item.get("root_cause") or ""),
            "reproduction": str(item.get("reproduction") or ""),
            "acceptance_criteria": str(item.get("acceptance_criteria") or ""),
            "detection_method": str(item.get("detection_method") or ""),
        }

    @staticmethod
    def _is_concrete(item: dict[str, Any]) -> bool:
        code = str(item.get("current_code") or "").strip()
        fix = str(item.get("suggested_fix") or "").strip()
        return bool(code) and bool(fix)

    @staticmethod
    def sanitize_json_literals(text: str) -> str:
        """Escape raw control characters and invalid escapes inside JSON string literals."""
        out: list[str] = []
        in_string = False
        escaped = False
        valid_escapes = {'"', "\\", "/", "b", "f", "n", "r", "t", "u"}
        for index, ch in enumerate(text):
            if escaped:
                out.append(ch)
                escaped = False
                continue
            if ch == "\\":
                if in_string and (
                    index + 1 == len(text) or text[index + 1] not in valid_escapes
                ):
                    out.append("\\\\")
                else:
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

    def parse(self, content: str, model: str) -> CodeReview:
        cleaned = self._clean_response(content)
        try:
            data = json.loads(self.sanitize_json_literals(cleaned))
            return self._code_review_from_dict(data, model)
        except (json.JSONDecodeError, ValueError):
            logger.debug("parse: JSON decode failed, trying text extraction")
        extracted = self.extract_outermost_json(cleaned)
        if extracted is not None:
            try:
                data = json.loads(self.sanitize_json_literals(extracted))
                return self._code_review_from_dict(data, model)
            except (json.JSONDecodeError, ValueError):
                logger.debug("parse: extracted JSON decode also failed")
        return self._parse_markdown_fallback(content, model)

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
        if not isinstance(data, dict):
            raise ReviewVerdictError("Structured review output must be an object.")
        target: dict[str, Any] = data
        nested = data.get("data")
        if isinstance(nested, dict):
            target = nested
        items_data = self._provided_collection(
            target,
            ("items", "issues", "findings"),
            "findings",
        )
        items: list[ReviewItem] = []
        for item_dict in items_data:
            if not isinstance(item_dict, dict):
                raise ReviewVerdictError("Each review item must be an object.")
            normalized = self.normalize_item_dict(item_dict)
            items.append(
                ReviewItem(
                    severity=normalized["severity"],
                    category=normalized["category"],
                    file_path=normalized["file"],
                    description=normalized["description"],
                    line=normalized["line"],
                    current_code=normalized["current_code"],
                    suggested_fix=normalized["suggested_fix"],
                    root_cause=normalized["root_cause"],
                    reproduction=normalized["reproduction"],
                    acceptance_criteria=normalized["acceptance_criteria"],
                    detection_method=normalized["detection_method"],
                    id=format(_uuid.uuid7().int, "04x")[:4],
                )
            )
        verdict = self._resolve_verdict(target.get("verdict"), items)
        reason = self._resolve_reason(target)
        summary_value = target.get("summary")
        if not isinstance(summary_value, str) or not summary_value.strip():
            raise ReviewVerdictError(
                "Review output must contain a non-empty explicit summary."
            )
        suggestions = self._review_items_from_collection(
            self._provided_collection(
                target,
                ("suggestions", "recommendations", "improvements", "recommended"),
                "suggestions",
            ),
            "suggestions",
        )
        praise = self._review_items_from_collection(
            self._provided_collection(
                target,
                ("praise", "strengths", "positives"),
                "praise",
            ),
            "praise",
        )
        return CodeReview(
            verdict=verdict,
            reason=reason,
            summary=summary_value.strip(),
            items=items,
            suggestions=suggestions,
            praise=praise,
            model_used=model,
        )
