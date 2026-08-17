"""Fixtures for ResponseFieldNormalizer — captured from real LLM responses."""

from __future__ import annotations

from typing import Any, ClassVar


class ResponseNormalizerFixtures:
    """Sample LLM response payloads captured from real Ollama outputs."""

    well_formed_issue: ClassVar[dict[str, Any]] = {
        "file": "src/app.py",
        "line": "42",
        "description": "Missing null check before dereference",
    }

    partial_issue: ClassVar[dict[str, Any]] = {
        "file": "src/utils.py",
        "description": "Use f-string instead of format()",
    }

    empty_issue: ClassVar[dict[str, Any]] = {}

    none_issue: ClassVar[dict[str, Any]] = {
        "file": None,
        "line": None,
        "description": None,
    }

    suggestions: ClassVar[list[dict[str, Any]]] = [
        {"description": "Consider using async/await", "file": "app.py"},
        {"description": "Add type hints to function signatures"},
    ]

    praise: ClassVar[list[dict[str, Any]]] = [
        {"description": "Clean separation of concerns"},
        {"description": "Good test coverage"},
    ]

    severity_samples: ClassVar[list[str]] = [
        "critical",
        "major",
        "minor",
        "info",
        "nitpick",
        "CRITICAL",
        "Major",
        "INFO",
    ]

    category_samples: ClassVar[list[str]] = [
        "bug",
        "security",
        "performance",
        "maintainability",
        "style",
        "BUG",
        "Security",
    ]

    reason_list: ClassVar[list[str]] = ["missing error handling", "no input validation"]

    retry_failures_single: ClassVar[list[str]] = ["missing_severity"]
    retry_failures_multiple: ClassVar[list[str]] = ["missing_severity", "invalid_category"]
    retry_failures_unknown: ClassVar[list[str]] = ["unknown_key"]

    description_dict: ClassVar[dict[str, Any]] = {"detail": "The function is too long", "line": "42"}
    description_list: ClassVar[list[str]] = ["Missing null check", "No input validation"]
    description_int: int = 404

    ensure_str_dict: ClassVar[dict[str, Any]] = {"key": "value", "status": "error"}
    ensure_str_list: ClassVar[list[int]] = [1, 2, 3]