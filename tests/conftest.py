"""Pytest fixtures for git_platform adapter integration tests.

Loads fixture data from tests/fixtures/*.json files.
"""

pytest_plugins = ["tests.fixtures.integration_fixtures", "tests.fixtures.auto_fixtures"]

import json
from pathlib import Path
from typing import Any

import pytest

from pr_auto_reviewer.presentation.polling_daemon import PollingDaemonConfig

FIXTURES_DIR = Path(__file__).parent / "fixtures"

def load_fixture(name: str) -> dict[str, Any]:
    """Load a fixture file by name (without .json extension)."""
    path = FIXTURES_DIR / f"{name}.json"
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    with open(path) as f:
        return json.load(f)


@pytest.fixture(scope="session")
def review_flow_fixtures() -> dict[str, Any]:
    """Review flow fixture data."""
    return load_fixture("review_flow_fixtures")




@pytest.fixture
def polling_daemon_config() -> PollingDaemonConfig:
    """PollingDaemonConfig for testing."""
    return PollingDaemonConfig(
        poll_interval_seconds=1,
        repos_filter=None,
        run_once=True,
    )

class _Call:
    """A simple call wrapper compatible with unittest.mock._Call's indexing.

    _Call((arg1, arg2)) → call
    call[0] → (arg1, arg2)   (positional args tuple)
    call[1] → {}             (keyword args dict)
    call[0][0] → arg1
    """

    def __init__(self, args: tuple, kwargs: dict | None = None) -> None:
        self._args = args
        self._kwargs = kwargs or {}

    def __getitem__(self, index):
        if index == 0:
            return self._args
        if index == 1:
            return self._kwargs
        raise IndexError(index)

class _StubReviewService:
    """Stub ReviewPullRequestUseCase that records executed commands.

    Provides MagicMock-compatible tracking attributes for migration ease.
    """

    def __init__(self) -> None:
        self.commands: list = []
        self.call_count = 0
        self.call_args_list: list = []
        self._last_call_args = None

    @property
    def call_args(self):
        """Return call_args for the most recent call (like MagicMock)."""
        return self._last_call_args

    def execute(self, command) -> None:
        self.commands.append(command)
        self.call_count = len(self.commands)
        self._last_call_args = _Call((command,))
        self.call_args_list.append(self._last_call_args)

    def assert_called_once(self) -> None:
        assert self.call_count == 1, f"Expected 1 call, got {self.call_count}"

    def assert_not_called(self) -> None:
        assert self.call_count == 0, f"Expected 0 calls, got {self.call_count}"

@pytest.fixture
def stub_review_service() -> _StubReviewService:
    """Stub ReviewPullRequestUseCase service."""
    return _StubReviewService()



class _FakeResponse:
    """A minimal fake requests.Response for Ollama adapter tests."""

    def __init__(self, json_data: dict | str | None, *, status_code: int = 200) -> None:
        self._json_data = json_data
        self.status_code = status_code

    def json(self) -> dict:
        if isinstance(self._json_data, dict):
            return self._json_data
        if isinstance(self._json_data, str):
            import json as _json
            return _json.loads(self._json_data)
        return {}

    def raise_for_status(self) -> None:
        pass

def _make_ollama_fake_post(response_fixture: str, *, raise_exc: Exception | None = None):
    """Build a fake requests.post that returns fixture-based responses."""
    import json as _json
    from pathlib import Path as _Path

    _fixtures_dir = _Path(__file__).parent / "fixtures" / "ollama_responses"

    def _fake_post(url, *, json=None, timeout=None, **kwargs):
        import requests as _requests
        if raise_exc is not None:
            raise raise_exc
        fixture_path = _fixtures_dir / response_fixture
        if fixture_path.suffix == ".txt":
            raw_text = fixture_path.read_text()
            return _FakeResponse(raw_text)
        return _FakeResponse(_json.loads(fixture_path.read_text()))

    return _fake_post

@pytest.fixture
def ollama_fake_post():
    """Fake requests.post that returns valid Ollama responses from fixtures.

    Use with monkeypatch.setattr in tests:

        monkeypatch.setattr(requests_module, "post", ollama_fake_post)
    """
    return _make_ollama_fake_post("response_with_response_field.json")

@pytest.fixture
def ollama_fake_post_error():
    """Fake requests.post that raises a RequestException (connection error)."""
    import requests as _requests
    return _make_ollama_fake_post("", raise_exc=_requests.RequestException("Connection error"))

@pytest.fixture
def ollama_fake_post_invalid_json():
    """Fake requests.post that returns invalid (non-JSON) text."""
    return _make_ollama_fake_post("invalid_json.txt")

@pytest.fixture
def ollama_fake_post_empty():
    """Fake requests.post that returns an empty response field."""
    return _make_ollama_fake_post("empty_response.json")
