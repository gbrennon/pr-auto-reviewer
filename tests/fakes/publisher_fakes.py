"""Spy client for platform publisher tests.

Records ``get``, ``get_raw``, and ``post`` calls alongside
``verify_token_for_pr`` so tests can assert API usage patterns.
"""

from __future__ import annotations

from typing import Any

from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from tests.fixtures.integration_fixtures import FixtureHttpClient


class SpyClient:
    """Wraps a ``FixtureHttpClient`` to record key API calls."""

    def __init__(
        self,
        delegate: FixtureHttpClient,
        fail_verify: Exception | None = None,
    ) -> None:
        self._delegate = delegate
        self._platform_mode = delegate._platform_mode
        self.verify_calls: list[PullRequestId] = []
        self.get_calls: list[tuple[str, dict]] = []
        self.get_raw_calls: list[tuple[str, dict]] = []
        self.post_calls: list[tuple[str, dict]] = []
        self._fail_verify = fail_verify

    def verify_token_for_pr(self, pr_id: PullRequestId) -> None:
        self.verify_calls.append(pr_id)
        if self._fail_verify is not None:
            raise self._fail_verify

    def get(self, path: str, **kwargs: Any) -> dict[str, Any]:
        self.get_calls.append((path, kwargs))
        return self._delegate.get(path, **kwargs)

    def get_raw(self, path: str, **kwargs: Any) -> str:
        self.get_raw_calls.append((path, kwargs))
        return self._delegate.get_raw(path, **kwargs)

    def post(self, path: str, payload: dict[str, Any], **kwargs: Any) -> Any:
        self.post_calls.append((path, kwargs))
        return self._delegate.post(path, payload, **kwargs)

    def __getattr__(self, name: str):
        return getattr(self._delegate, name)
