"""Fixtures that serve captured API data instead of real HTTP calls."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent

@pytest.fixture(scope="session")
def integration_data() -> dict[str, Any]:
    """Load the comprehensive integration fixture data."""
    path = FIXTURES_DIR / "integration_fixtures.json"
    with open(path) as f:
        return json.load(f)

class FixtureHttpClient:
    """HTTP client that returns fixture data instead of making real calls."""

    _platform_mode = "forgejo"

    def __init__(self, data: dict, scenario: str) -> None:
        self._data = data
        self._scenario = scenario
        self._base_url = "https://codeberg.org/api/v1"

    @property
    def base_url(self) -> str:
        return self._base_url

    def get(self, path: str, headers: dict[str, str] | None = None, *, repo: str | None = None, **params: Any) -> dict[str, Any]:
        http = self._data["http"]
        if "/issues/" in path and "/comments" in path:
            return http["get_comments"]
        if "/pulls/" in path and "/reviews" in path:
            result = http.get("get_reviews", {})
            if "_error" in result:
                raise RuntimeError(result["_error"])
            return result
        if "/git/trees" in path:
            result = http.get("get_tree", {})
            if "_error" in result:
                raise RuntimeError(result["_error"])
            return result
        return http["get_pull"]

    def get_raw(self, path: str, headers: dict[str, str] | None = None, *, repo: str | None = None) -> str:
        http = self._data["http"]
        if path.endswith(".diff"):
            return http["get_raw_diff"]
        raise RuntimeError(f"No fixture for get_raw: {path}")

    def post(self, path: str, body: dict[str, Any], *, repo: str | None = None) -> dict[str, Any]:
        return {"id": 999, "number": 99, "body": body.get("body", "")}

    def verify_token_for_pr(self, pr_id) -> None:
        pass

@pytest.fixture(params=["private", "public"])
def patched_client(integration_data, request):
    """Parametrized fixture HTTP client with captured data."""
    scenario = request.param
    return FixtureHttpClient(integration_data[scenario], scenario)

@pytest.fixture
def patched_private_client(integration_data):
    """Fixture HTTP client with private PR data."""
    return FixtureHttpClient(integration_data["private"], "private")

@pytest.fixture
def pr_fixture(request):
    """Parametrized fixture resolving to scenario name."""
    return request.param if hasattr(request, 'param') else "private"
