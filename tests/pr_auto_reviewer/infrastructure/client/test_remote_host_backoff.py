from __future__ import annotations

import pytest

from pr_auto_reviewer.domain.exceptions.remote_operation_quarantined_error import (
    RemoteOperationQuarantinedError,
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


class TestRemoteHostBackoff:
    def test_increases_delay_before_quarantine(self) -> None:
        clock = _Clock()
        backoff = RemoteHostBackoff(
            interval_seconds=10.0,
            interval_increment_seconds=5.0,
            threshold=3,
            quarantine_seconds=100.0,
            clock=clock.now,
            sleeper=clock.sleep,
        )

        backoff.record_failure("token:codeberg")
        backoff.before_operation("token:codeberg")
        backoff.record_failure("token:codeberg")
        backoff.before_operation("token:codeberg")

        assert clock.sleeps == [10.0, 15.0]

        backoff.record_failure("token:codeberg")

        with pytest.raises(RemoteOperationQuarantinedError):
            backoff.before_operation("token:codeberg")

    def test_quarantine_expires_and_success_resets_state(self) -> None:
        clock = _Clock()
        backoff = RemoteHostBackoff(
            interval_seconds=10.0,
            interval_increment_seconds=5.0,
            threshold=2,
            quarantine_seconds=20.0,
            clock=clock.now,
            sleeper=clock.sleep,
        )

        backoff.record_failure("token:codeberg")
        backoff.record_failure("token:codeberg")

        with pytest.raises(RemoteOperationQuarantinedError):
            backoff.before_operation("token:codeberg")

        clock.value += 20.0
        backoff.before_operation("token:codeberg")
        backoff.record_success("token:codeberg")
        backoff.record_failure("token:codeberg")
        backoff.before_operation("token:codeberg")

        assert clock.sleeps == [10.0]

    def test_success_resets_failure_streak(self) -> None:
        clock = _Clock()
        backoff = RemoteHostBackoff(clock=clock.now, sleeper=clock.sleep)

        backoff.record_failure("codeberg.org")
        backoff.record_failure("codeberg.org")
        backoff.record_success("codeberg.org")
        backoff.before_operation("codeberg.org")

        assert clock.sleeps == []

    def test_extracts_api_and_clone_hosts_without_credentials(self) -> None:
        assert (
            RemoteHostBackoff.host_from_url("https://codeberg.org/api/v1")
            == "codeberg.org"
        )
        assert (
            RemoteHostBackoff.host_from_url("git@codeberg.org:owner/repo.git")
            == "codeberg.org"
        )
        assert (
            RemoteHostBackoff.host_from_url(
                "https://api.github.com/owner/repo.git"
            )
            == "api.github.com"
        )
