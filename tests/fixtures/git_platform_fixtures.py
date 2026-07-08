"""Fixtures that load captured API response data for git_platform integration tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent

def _load(name: str) -> dict[str, Any]:
    path = FIXTURES_DIR / f"{name}.json"
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    with open(path) as f:
        return json.load(f)

@pytest.fixture
def http_client_fixtures() -> dict[str, Any]:
    """HTTP client captured responses."""
    return _load("http_client_fixtures")

@pytest.fixture
def comment_reader_fixtures() -> dict[str, Any]:
    """Comment reader captured responses."""
    return _load("comment_reader_fixtures")

@pytest.fixture
def comment_reader_scenario(request):
    """Parametrized fixture for comment_reader tests."""
    return request.getfixturevalue(request.param)

@pytest.fixture
def review_reader_fixtures() -> dict[str, Any]:
    """Review reader captured responses."""
    return _load("review_reader_fixtures")

@pytest.fixture
def review_reader_scenario(request):
    """Parametrized fixture for review_reader tests."""
    return request.getfixturevalue(request.param)

@pytest.fixture
def repository_context_fixtures() -> dict[str, Any]:
    """Repository context captured responses."""
    return _load("repository_context_fixtures")

@pytest.fixture
def repository_context_scenario(request):
    """Parametrized fixture for repository_context tests."""
    return request.getfixturevalue(request.param)

@pytest.fixture
def comment_publisher_fixtures() -> dict[str, Any]:
    """Comment publisher captured responses."""
    return _load("comment_publisher_fixtures")

@pytest.fixture
def issue_tracker_fixtures() -> dict[str, Any]:
    """Issue tracker captured responses."""
    return _load("issue_tracker_fixtures")

@pytest.fixture
def review_publisher_fixtures() -> dict[str, Any]:
    """Review publisher captured responses."""
    return _load("review_publisher_fixtures")
