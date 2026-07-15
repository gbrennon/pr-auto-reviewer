"""Spy client for PlatformReviewPublisherAdapter verify-token tests."""

from __future__ import annotations

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from tests.fixtures.integration_fixtures import FixtureHttpClient


class SpyClient:
    """Wraps a ``FixtureHttpClient`` to record ``verify_token_for_pr`` calls."""

    def __init__(
        self,
        delegate: FixtureHttpClient,
        fail_verify: Exception | None = None,
    ) -> None:
        self._delegate = delegate
        self._platform_mode = delegate._platform_mode
        self.verify_calls: list[PullRequestId] = []
        self._fail_verify = fail_verify

    def verify_token_for_pr(self, pr_id: PullRequestId) -> None:
        self.verify_calls.append(pr_id)
        if self._fail_verify is not None:
            raise self._fail_verify

    def __getattr__(self, name: str):
        return getattr(self._delegate, name)
