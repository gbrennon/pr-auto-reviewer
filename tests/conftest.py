"""Pytest fixtures for git_platform adapter integration tests.

Loads fixture data from tests/fixtures/*.json files.
"""

pytest_plugins = ["tests.fixtures.changeset_fixtures", "tests.fixtures.git_platform_fixtures", "tests.fixtures.integration_fixtures", "tests.fixtures.auto_fixtures"]

import json
from pathlib import Path
from typing import Any

import pytest

from pr_auto_reviewer.presentation.ports import (
    OpenPullRequest,
    RepoListerPort,
    PrListerPort,
)
from pr_auto_reviewer.presentation.polling_daemon import PollingDaemonConfig
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha

FIXTURES_DIR = Path(__file__).parent / "fixtures"

def load_fixture(name: str) -> dict[str, Any]:
    """Load a fixture file by name (without .json extension)."""
    path = FIXTURES_DIR / f"{name}.json"
    if not path.exists():
        pytest.skip(f"Fixture not found: {path}")
    with open(path) as f:
        return json.load(f)

@pytest.fixture(scope="session")
def pr_fixtures() -> dict[str, Any]:
    """PR fixture data (private and public PRs)."""
    return load_fixture("pr_fixtures")

@pytest.fixture(scope="session")
def context_fixtures() -> dict[str, Any]:
    """Repository context fixture data."""
    return load_fixture("context_fixtures")

@pytest.fixture
def private_pr_fixtures(pr_fixtures: dict) -> dict:
    """Fixtures for private PR (gbrennon/pr-auto-reviewer #53)."""
    return pr_fixtures["private_pr"]

@pytest.fixture
def public_pr_fixtures(pr_fixtures: dict) -> dict:
    """Fixtures for public PR (gbrennon/BitPill #95)."""
    return pr_fixtures["public_pr"]

@pytest.fixture
def user_fixtures(pr_fixtures: dict) -> dict:
    """Authenticated user fixture."""
    return pr_fixtures.get("user", {})

@pytest.fixture
def review_publisher(
    http_client: GitPlatformHttpClient,
    forgejo_token: str,
    user_fixtures: dict,
) -> GitReviewPublisherAdapter:
    """Review publisher adapter."""
    return GitReviewPublisherAdapter(
        http_client,
        reviewer_username=user_fixtures.get("login", "gbrennon"),
    )

@pytest.fixture(scope="session")
def review_flow_fixtures() -> dict[str, Any]:
    """Review flow fixture data."""
    return load_fixture("review_flow_fixtures")

@pytest.fixture
def mock_repo_lister(review_flow_fixtures: dict) -> RepoListerPort:
    """Mock RepoListerPort that returns fixture repos."""

    class MockRepoLister(RepoListerPort):
        def __init__(self, repos: list[str]) -> None:
            self._repos = repos

        def list_repos(self) -> list[str]:
            return self._repos

    repos_data = review_flow_fixtures.get("repos", [])
    return MockRepoLister([r["full_name"] for r in repos_data])

@pytest.fixture
def mock_pr_lister(review_flow_fixtures: dict) -> PrListerPort:
    """Mock PrListerPort that returns fixture PRs."""

    class MockPrLister(PrListerPort):
        def __init__(self, prs: list[OpenPullRequest]) -> None:
            self._prs = prs

        def list_open(self, repository: str) -> list[OpenPullRequest]:
            return self._prs

        def get_pr(self, repository: str, pr_number: int) -> OpenPullRequest | None:
            for p in self._prs:
                if p.pr_id.number == pr_number:
                    return p
            return None

    prs_data = review_flow_fixtures.get("open_prs", [])
    prs = []
    for pr in prs_data:
        if not pr.get("draft", False):
            prs.append(
                OpenPullRequest(
                    pr_id=PullRequestId(repository=pr["repo"], number=pr["number"]),
                    head_sha=CommitSha(pr["head"]["sha"]),
                    title=pr["title"],
                    is_draft=pr.get("draft", False),
                )
            )
    return MockPrLister(prs)

@pytest.fixture
def mock_pr_lister_with_drafts(review_flow_fixtures: dict) -> PrListerPort:
    """Mock PrListerPort that returns fixture PRs including drafts."""

    class MockPrLister(PrListerPort):
        def __init__(self, prs: list[OpenPullRequest]) -> None:
            self._prs = prs

        def list_open(self, repository: str) -> list[OpenPullRequest]:
            return self._prs

    prs_data = review_flow_fixtures.get("open_prs", [])
    prs = []
    for pr in prs_data:
        prs.append(
            OpenPullRequest(
                pr_id=PullRequestId(repository=pr["repo"], number=pr["number"]),
                head_sha=CommitSha(pr["head"]["sha"]),
                title=pr["title"],
                is_draft=pr.get("draft", False),
            )
        )
    return MockPrLister(prs)

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

    def execute(self, command) -> None:
        self.commands.append(command)
        self.call_count = len(self.commands)
        self._last_call_args = _Call((command,))
        self.call_args_list.append(self._last_call_args)

    @property
    def call_args(self):
        """Return call_args for the most recent call (like MagicMock)."""
        return self._last_call_args

    def assert_called_once(self) -> None:
        assert self.call_count == 1, f"Expected 1 call, got {self.call_count}"

    def assert_not_called(self) -> None:
        assert self.call_count == 0, f"Expected 0 calls, got {self.call_count}"

@pytest.fixture
def stub_review_service() -> _StubReviewService:
    """Stub ReviewPullRequestUseCase service."""
    return _StubReviewService()

@pytest.fixture
def sample_diff_content(review_flow_fixtures: dict) -> str:
    """Sample diff content from fixtures."""
    return review_flow_fixtures.get("sample_diff", "")

@pytest.fixture
def sample_tree_paths(review_flow_fixtures: dict) -> list[str]:
    """Sample tree paths from fixtures."""
    return review_flow_fixtures.get("tree_paths", [])

@pytest.fixture
def sample_llm_response_markdown(review_flow_fixtures: dict) -> str:
    """Sample LLM response in markdown format."""
    return review_flow_fixtures.get("llm_responses", {}).get("markdown_format", "")

@pytest.fixture
def sample_review_items(review_flow_fixtures: dict) -> list[dict]:
    """Sample review items from fixtures."""
    return review_flow_fixtures.get("review_items", [])

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
