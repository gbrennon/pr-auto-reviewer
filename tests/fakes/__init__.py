"""Re-exports of all fake classes used by infrastructure and presentation tests."""

from tests.fakes.fake_changeset_fetcher import FakeChangesetFetcher
from tests.fakes.fake_clone_url_resolver import FakeCloneUrlResolver
from tests.fakes.fake_fragment_repository import FakeFragmentRepository
from tests.fakes.fake_git_platform_http_client import FakeGitPlatformHttpClient
from tests.fakes.fake_http_client import FakeHttpClient
from tests.fakes.fake_llm_review import FakeLlmReview
from tests.fakes.fake_local_repository import FakeLocalRepository
from tests.fakes.fake_prompt_renderer import FakePromptRenderer
from tests.fakes.fake_pull_request_repository import FakePullRequestRepository
from tests.fakes.fake_repository_context import FakeRepositoryContext
from tests.fakes.fake_response import FakeResponse
from tests.fakes.fake_review_context_factory import FakeReviewContextFactory
from tests.fakes.fake_review_publisher import FakeReviewPublisher
from tests.fakes.fake_token_resolver import FakeTokenResolver
from tests.fakes.fake_verifier import FakeVerifier
from tests.fakes.spy_client import SpyClient

__all__ = [
    "FakeChangesetFetcher",
    "FakeCloneUrlResolver",
    "FakeFragmentRepository",
    "FakeGitPlatformHttpClient",
    "FakeHttpClient",
    "FakeLlmReview",
    "FakeLocalRepository",
    "FakePromptRenderer",
    "FakePullRequestRepository",
    "FakeRepositoryContext",
    "FakeResponse",
    "FakeReviewContextFactory",
    "FakeReviewPublisher",
    "FakeTokenResolver",
    "FakeVerifier",
    "SpyClient",
]