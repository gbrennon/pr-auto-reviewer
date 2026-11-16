"""Tests for the Forgejo CLI transport adapter."""

from dataclasses import dataclass

from pr_auto_reviewer.infrastructure.forgejo.fj_cli_client import FjCliClient


@dataclass
class FakeCommandRunner:
    """Return deterministic fj command results."""

    stdout: str = "{}"
    calls: list[list[str]] | None = None

    def run(self, command: list[str], input_text: str | None = None) -> str:
        del input_text
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
