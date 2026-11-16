"""Tests for the GitHub CLI transport adapter."""

import json
from dataclasses import dataclass

from pr_auto_reviewer.infrastructure.github.gh_cli_client import GhCliClient


@dataclass
class FakeCommandRunner:
    """Return deterministic command results without invoking gh."""

    stdout: str = "{}"
    calls: list[tuple[list[str], str | None]] | None = None

    def run(self, command: list[str], input_text: str | None = None) -> str:
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
