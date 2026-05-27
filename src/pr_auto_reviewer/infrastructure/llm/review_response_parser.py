"""ReviewResponseParser — parses raw LLM text into a CodeReview domain object."""

from __future__ import annotations

import json
import logging
import re

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
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
            json_text = inner
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

        logger.debug(
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
        issues = data.get("issues") or []
        if not issues:
            issues = ReviewResponseParser._find_items_in_dict(data)
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

        items = []
        for idx, issue in enumerate(issues, 1):
            file_path = (issue.get("file") or "").strip()
            if not file_path:
                logger.debug(
                    "Dropping non-actionable issue without file path: %r",
                    issue,
                )
                continue

            description = issue.get("description") or issue.get("details") or ""

            severity_str = issue.get("severity", "").strip().lower()
            if ItemSeverity.accepts(severity_str):
                severity = ItemSeverity.from_value(severity_str)
            else:
                severity, severity_str = ReviewResponseParser._infer_severity(
                    description
                )

            category_str = (issue.get("category") or issue.get("type") or "").strip()
            if not category_str:
                category_str = ReviewResponseParser._infer_type(
                    description, severity_str
                )
            category = IssueCategory.from_value(category_str)
            if not description:
                description = ReviewResponseParser._describe_change(
                    category.value, issue.get("file", "")
                )

            current_code = issue.get("current_code") or ""
            suggested_fix = issue.get("suggested_fix") or ""
            if not current_code.strip() or not suggested_fix.strip():
                logger.debug(
                    "Dropping non-actionable issue without concrete code: file=%s description=%r",
                    issue.get("file"),
                    description[:120],
                )
                continue

            items.append(
                ReviewItem(
                    number=len(items) + 1,
                    severity=severity,
                    category=category,
                    file_path=file_path,
                    line=issue.get("line", ""),
                    description=description,
                    current_code=current_code,
                    suggested_fix=suggested_fix,
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

        verdict = ReviewResponseParser._resolve_verdict(
            data.get("verdict"), items,
        )

        if not praise:
            praise = ReviewResponseParser._ensure_praise(summary, data)

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
    def _find_items_in_dict(data: dict) -> list[dict]:
        """Scan all values for any list of dicts that look like review items.

        Excludes known non-issue keys (suggestions, praise) since those
        are handled separately.  Looks for keys containing "issue" or
        "change" first; falls back to any remaining list with item-like
        dicts.
        """
        _ITEM_KEYS = {"file", "description", "details", "type", "severity", "line", "current_code"}
        _EXCLUDED_KEYS = {"suggestions", "praise", "summary", "reason", "reasons"}

        candidates: list[list[dict]] = []
        for key, val in data.items():
            if key in _EXCLUDED_KEYS:
                continue
            if isinstance(val, list) and len(val) > 0:
                if all(isinstance(v, dict) for v in val):
                    merged = set()
                    for v in val:
                        merged.update(v.keys())
                    if merged & _ITEM_KEYS:
                        candidates.append(val)

        if candidates:
            merged: list[dict] = []
            for c in candidates:
                for item in c:
                    merged.append(item)
            return merged
        return []

    @staticmethod
    def _parse_per_file_format(data: dict) -> list[dict]:
        """Convert model's per-file analysis output into issue-like dicts.

        Handles formats produced by qwen3:14b when it deviates from the
        expected schema:

            Format A — list of strings per file (paths as keys):
              {
                "path/to/file.py": ["code line 1", "code line 2", ...]
              }

            Format B — list of item dicts per file (paths as keys):
              {
                "path/to/file.py": [
                  {"type": "add", "content": "description", ...}
                ]
              }

            Format C — ``files`` array with ``path``/``changes`` keys:
              {
                "files": [
                  {"path": "file.py", "changes": ["line1", ...]},
                  {"path": "file2.py", "changes": []}
                ]
              }
        """
        _KNOWN_KEYS = {
            "deleted", "issues", "praise", "suggestions", "summary",
            "reason", "reasons", "verdict", "verdicts", "changes",
            "file_paths", "file", "line",
        }
        _INNER_MAP = {"content": "description", "change": "description",
                       "location": "line"}
        issues: list[dict] = []

        # Format C: "files" array with path/changes
        files_val = data.get("files")
        if isinstance(files_val, list):
            for entry in files_val:
                if not isinstance(entry, dict):
                    continue
                file_path = entry.get("path", "")
                changes = entry.get("changes")
                if isinstance(changes, list):
                    code_lines = [c for c in changes if isinstance(c, str)]
                    if code_lines:
                        issues.append({
                            "file": file_path,
                            "description": f"Changes in {file_path}",
                            "current_code": "\n".join(code_lines),
                        })

        for key, val in data.items():
            if key in _KNOWN_KEYS or key == "files":
                continue
            if isinstance(val, dict):
                # Format D: {"file.py": {"changes": ["desc1", "desc2"]}}
                changes = val.get("changes")
                if isinstance(changes, list):
                    desc_lines = [c for c in changes if isinstance(c, str)]
                    if desc_lines:
                        desc = "Changes in " + key + ": " + "; ".join(desc_lines)
                        issues.append({
                            "file": key,
                            "description": desc,
                        })
                continue
            if not isinstance(val, list) or len(val) == 0:
                continue
            if all(isinstance(v, str) for v in val):
                # Format A: plain strings per file
                code_lines = "\n".join(val)
                issues.append({
                    "file": key,
                    "description": f"Changes in {key}",
                    "current_code": code_lines,
                })
            elif all(isinstance(v, dict) for v in val):
                # Format B: item dicts per file
                for item in val:
                    mapped: dict[str, str] = {"file": key}
                    for k, v in item.items():
                        if isinstance(v, str):
                            mapped[_INNER_MAP.get(k, k)] = v
                    issues.append(mapped)
        return issues

    @staticmethod
    def _describe_change(change_type: str, file_path: str) -> str:
        """Generate a human-readable description from a change item's type and file."""
        _type_descriptions = {
            "added": "Added",
            "modified": "Modified",
            "changed": "Changed",
            "log_addition": "Added logging",
            "logging": "Added logging",
            "config_adjustment": "Adjusted configuration",
            "config": "Adjusted configuration",
            "refactor": "Refactored",
            "rename": "Renamed",
            "test_addition": "Added tests",
            "test": "Added tests",
            "documentation": "Updated documentation",
            "doc": "Updated documentation",
            "bugfix": "Fixed a bug",
            "bug_fix": "Fixed a bug",
            "bug": "Fixed a bug",
            "performance": "Improved performance",
            "dependency": "Updated dependency",
            "style": "Applied style change",
            "formatting": "Applied formatting change",
            "cleanup": "Cleaned up code",
            "dead_code_removal": "Removed dead code",
            "type_hint": "Added type hint",
            "type_hints": "Added type hints",
            "error_handling": "Improved error handling",
            "quality": "Improved code quality",
            "maintainability": "Improved maintainability",
        }
        base = _type_descriptions.get(change_type) or change_type.replace("_", " ").title()
        if file_path:
            return f"{base} in {file_path}"
        return base

    @staticmethod
    def _describe_code(change_type: str, file_path: str, description: str) -> tuple[str, str]:
        """Fallback current_code/suggested_fix — always empty.

        Only real code from the model is meaningful. Placeholder text
        like '# Change:' or 'logger.<level>(<message>)' is worse than
        showing nothing, so we return empty strings and the template
        suppresses the code block via its {% if %} guards.
        """
        return "", ""

    @staticmethod
    def _ensure_praise(summary: str, data: dict) -> list[dict]:
        """Generate fallback praise when the model provides none."""
        if summary:
            sentences = summary.replace("! ", ". ").replace("? ", ". ").split(". ")
            positive_markers = ("well", "good", "clean", "proper", "correct", "nice",
                                "solid", "great", "excellent", "improved", "clear",
                                "structured", "organized", "follows", "consistent")
            for sentence in sentences:
                lower = sentence.lower().strip()
                for marker in positive_markers:
                    if marker in lower and len(sentence) > 15:
                        return [{"description": sentence.strip() + "."}]
        file_count = len(data.get("file_paths", []))
        if data.get("issues") and len(data["issues"]) == 0:
            return [{"description": "The codebase changes follow project conventions and appear well-structured."}]
        return [{"description": "The changes are well-organized and maintain consistency with the existing codebase."}]

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
            "data loss", "corruption", "resource leak", "memory leak",
            "file handle", "connection pool", "sql injection",
            "improper", "broken", "missing validation",
        )):
            return ItemSeverity.MAJOR, "high"
        # Medium keywords
        if any(kw in desc for kw in (
            "error handling", "try except", "exception handling",
            "edge case", "boundary condition", "performance",
            "inefficient", "duplicate", "duplication", "redundant",
            "import", "circular", "mutable default", "side effect",
        )):
            return ItemSeverity.MINOR, "medium"
        # Low keywords — docs, style, cosmetic
        if any(kw in desc for kw in (
            "naming", "rename", "typo", "style", "todo",
            "unused", "dead code", "comment", "cosmetic",
            "readability", "whitespace", "documentation",
            "update readme", "add doc", "add documentation",
            "formatting", "convention",
        )):
            return ItemSeverity.INFO, "low"
        # Default to medium
        return ItemSeverity.MINOR, "medium"

    @staticmethod
    def _infer_type(description: str, severity_str: str) -> IssueCategory:
        """Infer issue type from description keywords."""
        desc = description.lower()
        if any(kw in desc for kw in (
            "security", "injection", "secret", "leak", "vulnerability",
            "exploit", "credential", "xss", "csrf", "auth bypass",
            "hardcoded",
        )):
            return IssueCategory.SECURITY
        if any(kw in desc for kw in (
            "bug", "error", "exception", "try", "except", "raise",
            "error handling", "crash", "race", "deadlock", "null pointer",
            "undefined", "unhandled", "logic bug", "wrong result",
            "data loss", "corruption", "resource leak", "memory leak",
            "file handle", "connection pool", "sql injection",
            "improper", "broken", "missing validation",
        )):
            return IssueCategory.BUG
        if any(kw in desc for kw in (
            "architecture", "design", "layer", "boundary", "god object",
            "tight coupling", "violation", "adapter", "port",
            "hexagonal", "solid", "srp", "single responsib",
            "open/closed", "liskov", "interface seg",
            "dependency inversion",
        )):
            return IssueCategory.DESIGN
        if any(kw in desc for kw in (
            "performance", "slow", "inefficient", "n+1", "query",
            "cache", "timeout",
        )):
            return IssueCategory.PERFORMANCE
        if any(kw in desc for kw in (
            "testability", "untestable", "hard to test",
            "difficult to test", "mock", "stub", "fixture",
        )):
            return IssueCategory.TESTABILITY
        if any(kw in desc for kw in (
            "documentation", "docstring", "comment", "readme",
            "doc", "docs",
        )):
            return IssueCategory.DOCUMENTATION
        if any(kw in desc for kw in (
            "test", "assert", "coverage", "edge case", "boundary",
        )):
            return IssueCategory.TEST
        if any(kw in desc for kw in (
            "typo", "spelling", "misspelling", "typo",
        )):
            return IssueCategory.TYPO
        if any(kw in desc for kw in (
            "maintainability", "complexity", "readability",
            "magic number", "nesting", "duplicate", "duplication",
            "dead code", "unused", "convention", "style",
            "formatting", "naming", "rename", "log", "logging",
            "debug", "config", "configuration", "setting", "env",
        )):
            return IssueCategory.MAINTAINABILITY
        # Default by severity
        if severity_str in ("critical", "high"):
            return IssueCategory.BUG
        return IssueCategory.QUALITY



    @staticmethod
    def _resolve_verdict(
        explicit: str | None, items: list[ReviewItem],
    ) -> ReviewVerdict:
        """Resolve verdict — prefer explicit JSON field, fall back to
        deriving from parsed item severities."""
        if explicit:
            value = explicit.strip().lower()
            if "changes" in value or "request" in value:
                return ReviewVerdict.CHANGES_REQUESTED
            if "approved" in value or value == "approve":
                return ReviewVerdict.APPROVED
            if "commented" in value:
                return ReviewVerdict.COMMENTED
        return ReviewResponseParser._determine_verdict(items)

    @staticmethod
    def _determine_verdict(items: list[ReviewItem]) -> ReviewVerdict:
        """Determine verdict based on parsed item severities."""
        for item in items:
            if item.severity in (ItemSeverity.CRITICAL, ItemSeverity.MAJOR):
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
            file_path = match.group("file_path").strip() or None

            items.append(
                ReviewItem(
                    number=idx,
                    severity=ItemSeverity.from_value(match.group("severity")),
                    category=IssueCategory.from_value(match.group("category")),
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
