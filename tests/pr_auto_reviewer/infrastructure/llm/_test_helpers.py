"""Test helpers for OllamaExploratoryChatAdapter tests."""

from __future__ import annotations

import json
from typing import Any


class TestHelpers:
    """Helper methods for test data generation."""

    @staticmethod
    def make_verdict_json(
        verdict: str = "CHANGES_REQUESTED",
        issues: list[dict[str, Any]] | None = None,
    ) -> str:
        """Build a minimal verdict JSON response string."""
        if issues is None:
            issues = [
                {
                    "file": "src/foo.py",
                    "line": "42",
                    "severity": "major",
                    "category": "security",
                    "description": "SQL injection risk",
                    "current_code": "query = 'SELECT * FROM users WHERE id = ' + uid",
                    "suggested_fix": "query = 'SELECT * FROM users WHERE id = %s'",
                }
            ]
        return json.dumps(
            {
                "verdict": verdict,
                "summary": "Found issues in review",
                "issues": issues,
                "suggestions": [],
                "praise": [],
            }
        )

    @staticmethod
    def make_action_json(action: str, args: str) -> str:
        """Build a JSON tool-call response string."""
        return json.dumps({"action": action, "args": args})


class _FakeStreamingResponse:
    """Minimal fake requests.Response with streaming iter_lines."""

    def __init__(self, content: str, *, status_code: int = 200) -> None:
        self._content = content
        self.status_code = status_code

    def raise_for_status(self) -> None:
        pass

    def iter_lines(self, decode_unicode: bool) -> list[str]:
        """Simulate NDJSON chunks — one chunk for content, then a done marker."""
        return [
            json.dumps({"message": {"content": self._content}, "done": False}),
            json.dumps({"message": {"content": ""}, "done": True}),
        ]