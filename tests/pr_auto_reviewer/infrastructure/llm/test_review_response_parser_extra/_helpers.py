"""Shared helpers, fixtures, and imports for the split test modules."""

import pytest

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.exceptions.review_verdict_error import ReviewVerdictError
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)


def _prose_issues_content() -> str:
    return (
        "### Issues\n\n"
        "1. Unused import in src/main.py\n\n"
        "The `os` module is imported but never referenced.\n\n"
        "**Current Code:**\n```python\nimport os\n```\n\n"
        "**Fix:**\n```python\nimport sys\n```\n\n"
        "2. Magic number in config.py\n\n"
        "The timeout value is a raw literal.\n\n"
        "**Current Code:**\n```python\ntimeout = 30\n```\n\n"
        "**Fix:**\n```python\ntimeout = TIMEOUT_SECONDS\n```\n"
    )


def _prose_flat_content() -> str:
    return (
        "#### 1. Unused import in src/main.py\n\n"
        "The `os` module is imported but never referenced.\n\n"
        "**Current Code:**\n```python\nimport os\n```\n\n"
        "**Fix:**\n```python\nimport sys\n```\n\n"
        "#### 2. Magic number in config.py\n\n"
        "The timeout value is a raw literal.\n\n"
        "**Current Code:**\n```python\ntimeout = 30\n```\n\n"
        "**Fix:**\n```python\ntimeout = TIMEOUT_SECONDS\n```\n"
    )


def json_loads(text: str) -> dict:
    import json

    return json.loads(text)

__all__ = ['IssueCategory', 'ItemSeverity', 'ReviewItem', 'ReviewResponseParser', 'ReviewVerdict', 'ReviewVerdictError', '_prose_flat_content', '_prose_issues_content', 'json_loads', 'pytest']
