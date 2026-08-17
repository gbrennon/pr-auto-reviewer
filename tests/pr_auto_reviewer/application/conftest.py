"""Shared mock fixtures for application-layer tests.

Application services depend on outbound ports. Tests inject simple
unittest.mock mocks defined here, then configure return values per test.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_pr_repository() -> MagicMock:
    """Mock PullRequestRepository."""
    return MagicMock()


@pytest.fixture
def mock_review_reader() -> MagicMock:
    """Mock ReviewReaderPort."""
    return MagicMock()


@pytest.fixture
def mock_issue_tracker() -> MagicMock:
    """Mock IssueTrackerPort."""
    return MagicMock()


@pytest.fixture
def mock_comment_reader() -> MagicMock:
    """Mock CommentReaderPort."""
    return MagicMock()


@pytest.fixture
def mock_comment_publisher() -> MagicMock:
    """Mock CommentPublisherPort."""
    return MagicMock()


@pytest.fixture
def mock_changeset_fetcher() -> MagicMock:
    """Mock ChangesetFetcherPort."""
    return MagicMock()


@pytest.fixture
def mock_review_context_factory() -> MagicMock:
    """Mock ReviewContextFactoryPort."""
    return MagicMock()


@pytest.fixture
def mock_llm_review() -> MagicMock:
    """Mock LlmReviewPort."""
    return MagicMock()


@pytest.fixture
def mock_review_publisher() -> MagicMock:
    """Mock ReviewPublisherPort."""
    return MagicMock()


@pytest.fixture
def mock_chat_port() -> MagicMock:
    """Mock AgentChatPort."""
    return MagicMock()


@pytest.fixture
def mock_tool_factory() -> MagicMock:
    """Mock verifier tool factory callable."""
    return MagicMock()


@pytest.fixture
def mock_response_parser() -> MagicMock:
    """Mock ResponseParserPort."""
    return MagicMock()


@pytest.fixture
def mock_reason_builder() -> MagicMock:
    """Mock ReasonBuilderPort."""
    return MagicMock()


@pytest.fixture
def mock_token_verifier() -> MagicMock:
    """Mock TokenVerifierPort."""
    return MagicMock()


@pytest.fixture
def mock_command_bus() -> MagicMock:
    """Mock CommandBusPort."""
    return MagicMock()
