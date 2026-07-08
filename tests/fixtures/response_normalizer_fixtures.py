"""Fixtures for ResponseFieldNormalizer — captured from real LLM responses."""

from __future__ import annotations

from typing import Any


class ResponseNormalizerFixtures:
    """Sample LLM response payloads captured from real Ollama outputs."""

    # A well-formed issue from a real LLM review response
    well_formed_issue: dict[str, Any] = {
        "file": "src/app.py",
        "line": "42",
        "description": "Missing null check before dereference",
    }

    # An issue with missing optional fields (LLM sometimes omits line)
    partial_issue: dict[str, Any] = {
        "file": "src/utils.py",
        "description": "Use f-string instead of format()",
    }

    # Empty issue dict (LLM hallucination)
    empty_issue: dict[str, Any] = {}

    # Issue with None values (LLM sometimes sends null)
    none_issue: dict[str, Any] = {
        "file": None,
        "line": None,
        "description": None,
    }

    # Well-formed suggestions list
    suggestions: list[dict[str, Any]] = [
        {"description": "Consider using async/await", "file": "app.py"},
        {"description": "Add type hints to function signatures"},
    ]

    # Praise items
    praise: list[dict[str, Any]] = [
        {"description": "Clean separation of concerns"},
        {"description": "Good test coverage"},
    ]

    # Various severity values from real LLM outputs
    severity_samples: list[str] = [
        "critical",
        "major",
        "minor",
        "info",
        "nitpick",
        "CRITICAL",
        "Major",
        "INFO",
    ]

    # Various category values from real LLM outputs
    category_samples: list[str] = [
        "bug",
        "security",
        "performance",
        "maintainability",
        "style",
        "BUG",
        "Security",
    ]

    # Reason as list (some LLMs return array)
    reason_list: list[str] = ["missing error handling", "no input validation"]

    # Retry prompt failures
    retry_failures_single: list[str] = ["missing_severity"]
    retry_failures_multiple: list[str] = ["missing_severity", "invalid_category"]
    retry_failures_unknown: list[str] = ["unknown_key"]
