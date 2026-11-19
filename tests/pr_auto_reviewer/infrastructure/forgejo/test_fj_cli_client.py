"""Tests for the Forgejo CLI transport adapter."""

from dataclasses import dataclass

from pr_auto_reviewer.infrastructure.forgejo.fj_cli_client import FjCliClient

_PR_VIEW = """feat: add tui settings view #42
By gbrennon — Open — +72 -1
From `feat/settings-tui` into `main`

> Motivation
> Add a settings view.
"""

_COMMITS = """commit d111a6d3b78d55efe916223b2ef16a1fe6db860f (+72, -1)
Author: Glauber Brennon <glauberbrennon@gmail.com>
"""


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

    def test_pull_request_view_parses_human_readable_fj_output(self) -> None:
        class PullRequestRunner(FakeCommandRunner):
            def run(self, command: list[str], input_text: str | None = None) -> str:
                del input_text
                if self.calls is None:
                    self.calls = []
                self.calls.append(command)
                return _COMMITS if command[-1] == "commits" else _PR_VIEW

        runner = PullRequestRunner()
        client = FjCliClient(runner=runner)

        result = client.get("/repos/owner/repo/pulls/42")

        assert result == {
            "number": 42,
            "title": "feat: add tui settings view",
            "body": "Motivation\nAdd a settings view.",
            "head": {"sha": "d111a6d3b78d55efe916223b2ef16a1fe6db860f"},
            "base": {"ref": "main"},
            "draft": False,
            "requested_reviewers": [],
            "updated_at": "",
        }
        assert runner.calls == [
            ["fj", "pr", "view", "owner/repo#42"],
            ["fj", "pr", "view", "owner/repo#42", "commits"],
        ]

    def test_empty_comments_are_returned_as_an_empty_collection(self) -> None:
        runner = FakeCommandRunner(stdout="")
        client = FjCliClient(runner=runner)

        result = client.get("/repos/owner/repo/issues/42/comments")

        assert result == []
        assert runner.calls == [["fj", "pr", "view", "owner/repo#42", "comments"]]

    def test_comment_post_uses_fj_pr_comment(self) -> None:
        runner = FakeCommandRunner(stdout="commented")
        client = FjCliClient(runner=runner)

        result = client.post(
            "/repos/owner/repo/issues/42/comments", {"body": "Looks good"}
        )

        assert result == {}
        assert runner.calls == [["fj", "pr", "comment", "owner/repo#42", "Looks good"]]
