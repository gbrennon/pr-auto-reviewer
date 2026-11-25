from __future__ import annotations

from typing import Any

import pytest
import requests

from pr_auto_reviewer.infrastructure.client.preflight.requests_http_client import (
    RequestsHttpClient,
)
from pr_auto_reviewer.infrastructure.client.remote_host_backoff import (
    RemoteHostBackoff,
)


class _Clock:
    def __init__(self) -> None:
        self.value = 100.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds


class _Response:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class TestRequestsHttpClient:
    def test_transport_failures_wait_before_fourth_request(self, monkeypatch) -> None:
        clock = _Clock()
        backoff = RemoteHostBackoff(
            threshold=4, clock=clock.now, sleeper=clock.sleep,
        )
        attempts = 0

        def fake_get(*args: Any, **kwargs: Any) -> _Response:
            nonlocal attempts
            attempts += 1
            if attempts <= 3:
                raise requests.ConnectionError("connection refused")
            return _Response(200)

        monkeypatch.setattr(requests, "get", fake_get)
        client = RequestsHttpClient(
            "https://api.github.com",
            remote_host_backoff=backoff,
        )

        for _ in range(3):
            with pytest.raises(requests.ConnectionError):
                client.get("/user", headers={})

        client.get("/user", headers={})

        assert clock.sleeps == [60.0, 120.0, 180.0]

    def test_non_retryable_response_resets_mixed_retryable_streak(
        self, monkeypatch,
    ) -> None:
        clock = _Clock()
        backoff = RemoteHostBackoff(clock=clock.now, sleeper=clock.sleep)
        responses = [
            _Response(500),
            _Response(500),
            _Response(401),
            _Response(500),
            _Response(200),
        ]

        def fake_get(*args: Any, **kwargs: Any) -> _Response:
            return responses.pop(0)

        monkeypatch.setattr(requests, "get", fake_get)
        client = RequestsHttpClient(
            "https://api.github.com",
            remote_host_backoff=backoff,
        )

        for _ in range(5):
            client.get("/user", headers={})

        assert clock.sleeps == [60.0, 120.0, 60.0]
