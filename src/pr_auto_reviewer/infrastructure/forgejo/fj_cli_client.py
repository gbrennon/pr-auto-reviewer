"""Forgejo CLI transport implementing the existing platform client surface."""

from __future__ import annotations

import re
from typing import Any

from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from .command_runner import CommandRunner
from .subprocess_command_runner import SubprocessCommandRunner


class FjCliClient(GitPlatformHttpClient):
    """Use authenticated ``fj`` pull-request commands instead of HTTP."""

    def __init__(
        self,
        *,
        client_label: str = "",
        runner: CommandRunner | None = None,
    ) -> None:
        super().__init__(
            "https://codeberg.org/api/v1",
            "",
            platform_mode="forgejo",
            client_label=client_label,
        )
        self._runner = runner or SubprocessCommandRunner()

    def get(self, path: str, headers: dict[str, str] | None = None, *, repo: str | None = None, **params: Any) -> Any:
        """Read a supported Forgejo resource through ``fj``."""
        del headers, repo, params
        if path.endswith(("/reviews", "/timeline")):
            return []
        output = self._runner.run(self._view_command(path))
        if self._is_pull_request_view(path):
            return self._parse_pull_request_view(path, output)
        if not output.strip():
            return []
        return output

    def get_raw(self, path: str, headers: dict[str, str] | None = None, *, repo: str | None = None) -> str:
        """Read a pull-request diff through ``fj pr view ... diff``."""
        del headers, repo
        return self._runner.run(self._view_command(path))

    def post(self, path: str, body: dict[str, Any], *, repo: str | None = None) -> dict[str, Any]:
        """Publish comments or issues through supported ``fj`` commands."""
        match = re.match(r"/repos/([^/]+/[^/]+)/issues/(\d+)/comments$", path)
        if match:
            repository, number = match.groups()
            self._runner.run(
                ["fj", "pr", "comment", f"{repository}#{number}", str(body.get("body", ""))]
            )
            return {}
        if path.endswith("/issues") and repo:
            self._runner.run(
                [
                    "fj", "issue", "create", "--repo", repo, "--no-template",
                    str(body.get("title", "")), "--body", str(body.get("body", "")),
                ]
            )
            return {}
        raise RuntimeError(f"fj CLI does not expose a command for POST {path}")

    def is_capability_available(self, repo: str) -> bool:
        """Treat the authenticated fj session as the capability boundary."""
        del repo
        return True

    @staticmethod
    def _is_pull_request_view(path: str) -> bool:
        return bool(re.fullmatch(r"/repos/[^/]+/[^/]+/pulls/\d+", path))

    def _parse_pull_request_view(self, path: str, output: str) -> dict[str, object]:
        repository, number = re.fullmatch(
            r"/repos/([^/]+/[^/]+)/pulls/(\d+)", path
        ).groups()
        lines = output.splitlines()
        title_match = re.match(r"^(.*?)\s+#(\d+)$", lines[0]) if lines else None
        branch_match = re.search(
            r"From `([^`]+)` into `([^`]+)`", output
        )
        commits = self._runner.run(
            ["fj", "pr", "view", f"{repository}#{number}", "commits"]
        )
        sha_match = re.search(r"^commit ([0-9a-f]{7,40})", commits, re.MULTILINE)
        body = "\n".join(
            line[2:] for line in lines if line.startswith("> ")
        )
        if not title_match or not branch_match or not sha_match:
            raise RuntimeError(
                f"fj returned an unparseable pull request for {repository}#{number}"
            )
        return {
            "number": int(title_match.group(2)),
            "title": title_match.group(1),
            "body": body,
            "head": {"sha": sha_match.group(1)},
            "base": {"ref": branch_match.group(2)},
            "draft": False,
            "requested_reviewers": [],
            "updated_at": "",
        }

    @staticmethod
    def _view_command(path: str) -> list[str]:
        match = re.match(r"/repos/([^/]+/[^/]+)/pulls/(\d+)(.*)$", path)
        if match:
            repository, number, suffix = match.groups()
            command = ["fj", "pr", "view", f"{repository}#{number}"]
            if suffix == ".diff":
                command.append("diff")
            elif suffix == "/comments":
                command.append("comments")
            return command
        comment_match = re.fullmatch(
            r"/repos/([^/]+/[^/]+)/issues/(\d+)/comments", path
        )
        if comment_match:
            repository, number = comment_match.groups()
            return ["fj", "pr", "view", f"{repository}#{number}", "comments"]
        raise RuntimeError(f"fj CLI does not expose a command for GET {path}")
