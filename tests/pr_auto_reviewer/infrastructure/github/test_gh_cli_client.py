"""Tests for the GitHub CLI transport adapter."""

import json
from dataclasses import dataclass

from pr_auto_reviewer.infrastructure.github.gh_cli_client import GhCliClient


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

@dataclass
class FakeCommandRunner:
    """Return deterministic command results without invoking gh."""

    stdout: str = "{}"
    failures_remaining: int = 0
    calls: list[tuple[list[str], str | None]] | None = None

    def run(self, command: list[str], input_text: str | None = None) -> str:
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise RuntimeError("remote command failed")
        if self.calls is None:
            self.calls = []
        self.calls.append((command, input_text))
        return self.stdout


class TestGhCliClient:
    """Verify gh command construction and response decoding."""

    def test_get_uses_authenticated_gh_api(self) -> None:
        runner = FakeCommandRunner(stdout=json.dumps({"number": 42}))
        client = GhCliClient(runner=runner)

        result = client.get("/repos/owner/repo/pulls/42", state="open")

        assert result == {"number": 42}
        assert runner.calls == [
            (
                [
                    "gh",
                    "api",
                    "/repos/owner/repo/pulls/42?state=open",
                    "--method",
                    "GET",
                ],
                None,
            )
        ]

    def test_post_sends_json_without_token_arguments(self) -> None:
        runner = FakeCommandRunner(stdout=json.dumps({"id": 7}))
        client = GhCliClient(runner=runner)

        result = client.post("/repos/owner/repo/issues", {"title": "Fix"})

        assert result == {"id": 7}
        assert runner.calls == [
            (
                [
                    "gh",
                    "api",
                    "/repos/owner/repo/issues",
                    "--method",
                    "POST",
                    "--input",
                    "-",
                ],
                '{"title": "Fix"}',
            )
        ]

    def test_command_failures_use_shared_remote_backoff(self) -> None:
        clock = _Clock()
        backoff = RemoteHostBackoff(
            threshold=4, clock=clock.now, sleeper=clock.sleep,
        )
        runner = FakeCommandRunner(failures_remaining=3)
        client = GhCliClient(runner=runner, remote_host_backoff=backoff)

        for _ in range(3):
            try:
                client.get("/user")
            except RuntimeError:
                pass
            else:
                raise AssertionError("expected CLI command failure")

        assert client.get("/user") == {}
        assert clock.sleeps == [60.0, 120.0, 180.0]
