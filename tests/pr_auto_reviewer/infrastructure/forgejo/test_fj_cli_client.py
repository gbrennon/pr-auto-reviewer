"""Tests for the Forgejo CLI transport adapter."""

from dataclasses import dataclass

from pr_auto_reviewer.infrastructure.forgejo.fj_cli_client import FjCliClient

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
    """Return deterministic fj command results."""
    stdout: str = "{}"
    failures_remaining: int = 0
    calls: list[list[str]] | None = None

    def run(self, command: list[str], input_text: str | None = None) -> str:
        del input_text
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise RuntimeError("remote command failed")
        if self.calls is None:
            self.calls = []
        self.calls.append(command)
        return self.stdout


class TestFjCliClient:
    """Verify Forgejo CLI command construction."""

    def test_pull_request_view_uses_fj_pr_view(self) -> None:
        runner = FakeCommandRunner(stdout='{"number": 42}')
        client = FjCliClient(runner=runner)

        result = client.get("/repos/owner/repo/pulls/42")

        assert result == {"number": 42}
        assert runner.calls == [["fj", "pr", "view", "owner/repo#42"]]

    def test_comment_post_uses_fj_pr_comment(self) -> None:
        runner = FakeCommandRunner(stdout="commented")
        client = FjCliClient(runner=runner)

        result = client.post(
            "/repos/owner/repo/issues/42/comments", {"body": "Looks good"}
        )

        assert result == {}
        assert runner.calls == [["fj", "pr", "comment", "owner/repo#42", "Looks good"]]

    def test_command_failures_use_shared_remote_backoff(self) -> None:
        clock = _Clock()
        backoff = RemoteHostBackoff(
            threshold=4, clock=clock.now, sleeper=clock.sleep,
        )
        runner = FakeCommandRunner(failures_remaining=3)
        client = FjCliClient(runner=runner, remote_host_backoff=backoff)

        for _ in range(3):
            try:
                client.get("/repos/owner/repo/pulls/42")
            except RuntimeError:
                pass
            else:
                raise AssertionError("expected CLI command failure")

        assert client.get("/repos/owner/repo/pulls/42") == {}
        assert clock.sleeps == [60.0, 120.0, 180.0]
