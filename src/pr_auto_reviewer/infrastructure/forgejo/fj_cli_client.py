"""Forgejo CLI transport implementing the existing platform client surface."""

from __future__ import annotations

import json
import re
import subprocess
from typing import Any, Protocol

from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)


class CommandRunner(Protocol):
    """Run an authenticated command and return stdout."""

    def run(self, command: list[str], input_text: str | None = None) -> str:
        """Execute a command."""
        ...


class SubprocessCommandRunner:
    """Run commands through the local process environment."""

    def run(self, command: list[str], input_text: str | None = None) -> str:
        """Execute a command and raise when the CLI reports failure."""
        result = subprocess.run(
            command,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or "Forgejo CLI command failed")
        return result.stdout


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
        command = self._view_command(path)
        output = self._runner.run(command)
        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                "fj must provide machine-readable JSON for platform integration"
            ) from exc

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
                [
                    "fj",
                    "pr",
                    "comment",
                    f"{repository}#{number}",
                    str(body.get("body", "")),
                ]
            )
            return {}
        if path.endswith("/issues") and repo:
            self._runner.run(
                [
                    "fj",
                    "issue",
                    "create",
                    "--repo",
                    repo,
                    "--no-template",
                    str(body.get("title", "")),
                    "--body",
                    str(body.get("body", "")),
                ]
            )
            return {}
        raise RuntimeError(f"fj CLI does not expose a command for POST {path}")

    def is_capability_available(self, repo: str) -> bool:
        """Treat the authenticated fj session as the capability boundary."""
        del repo
        return True

    @staticmethod
    def _view_command(path: str) -> list[str]:
        match = re.match(r"/repos/([^/]+/[^/]+)/pulls/(\d+)(.*)$", path)
        if not match:
            raise RuntimeError(f"fj CLI does not expose a command for GET {path}")
        repository, number, suffix = match.groups()
        command = ["fj", "pr", "view", f"{repository}#{number}"]
        if suffix == ".diff":
            command.append("diff")
        elif suffix == "/comments":
            command.append("comments")
        return command
