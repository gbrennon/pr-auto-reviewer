"""Pytest fixtures for git_platform adapter integration tests.

Loads fixture data from tests/fixtures/*.json files.
"""

pytest_plugins = ["tests.fixtures.integration_fixtures"]

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
    """Stub ReviewPullRequestPort that records executed commands.

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

    def execute(self, command) -> bool:
        self.commands.append(command)
        self.call_count = len(self.commands)
        self._last_call_args = _Call((command,))
        self.call_args_list.append(self._last_call_args)
        return True

    def assert_called_once(self) -> None:
        assert self.call_count == 1, f"Expected 1 call, got {self.call_count}"

    def assert_not_called(self) -> None:
        assert self.call_count == 0, f"Expected 0 calls, got {self.call_count}"

@pytest.fixture
def stub_review_service() -> _StubReviewService:
    """Stub ReviewPullRequestPort service."""
    return _StubReviewService()
