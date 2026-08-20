"""Behavior-level checks for review payloads — no default-value leaks.

These helpers are deliberately implementation-agnostic: they inspect the
JSON a review entrypoint produced and fail if any top-level or item field
carries a default/empty/placeholder value. They are shared by the fixture
capture tests and the VCR capture/replay e2e tests.
"""

from __future__ import annotations

import re
from typing import Any

DEFAULT_TOKENS: tuple[str, ...] = (
    "no issues found across all review phases",
    "no structured verdict",
    "application could not extract",
    "no explanation provided",
    "review completed without action items",
    "not found",
    "not set",
    "unknown",
    "unset",
    "<fill",
    "todo",
    "example",
    "lorem",
)
_PLACEHOLDER_RE = re.compile(r"(step|placeholder|put your|your text|datetime\.now)", re.IGNORECASE)


class ReviewPayloadBehaviorChecker:
    """Assert a review JSON payload has no empty or default values."""

    TOP_LEVEL = ("verdict", "reason", "summary", "items", "suggestions", "praise", "model_used")
    ITEM_LEVEL = ("severity", "category", "file_path", "description", "line", "id", "current_code", "suggested_fix")
    SUGGESTION_LEVEL = ("severity", "category", "file_path", "description", "line", "id", "current_code", "suggested_fix")
    PRAISE_LEVEL = ("severity", "category", "file_path", "description", "id", "current_code", "suggested_fix")

    def violations(self, payload: dict[str, Any]) -> list[str]:
        """Return a list of human-readable default/empty violations, [] if clean."""
        problems: list[str] = []
        if not isinstance(payload, dict):
            return ["payload is not an object"]
        for key in self.TOP_LEVEL:
            value = payload.get(key)
            if self._is_empty(value):
                problems.append(f"top-level {key} is empty or a default")
        for value in (payload.get("verdict"), payload.get("reason"), payload.get("summary")):
            if isinstance(value, str) and self._looks_like_default(value):
                problems.append(f"string field uses a default phrase: {value[:60]!r}")
        for kind, entries, fields in (
            ("item", payload.get("items"), self.ITEM_LEVEL),
            ("suggestion", payload.get("suggestions"), self.SUGGESTION_LEVEL),
            ("praise", payload.get("praise"), self.PRAISE_LEVEL),
        ):
            if not isinstance(entries, list):
                continue
            for i, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    problems.append(f"{kind} #{i} is not an object")
                    continue
                for field in fields:
                    if self._is_empty(entry.get(field)):
                        problems.append(f"{kind} #{i}.{field} is empty")
        return problems

    def _is_empty(self, value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, str):
            return not value.strip() or value.strip().lower() in ("none", "null", "n/a", "na")
        return False

    def _looks_like_default(self, text: str) -> bool:
        lowered = text.lower()
        if any(token in lowered for token in DEFAULT_TOKENS):
            return True
        return bool(_PLACEHOLDER_RE.search(text))