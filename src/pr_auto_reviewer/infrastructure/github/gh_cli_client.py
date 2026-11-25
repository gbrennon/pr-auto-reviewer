"""GitHub CLI transport implementing the existing platform client surface."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.infrastructure.client.remote_host_backoff import (
    RemoteHostBackoff,
)
from .command_runner import CommandRunner
from .subprocess_command_runner import SubprocessCommandRunner


class GhCliClient(GitPlatformHttpClient):
    """Use an authenticated ``gh api`` session instead of HTTP requests."""

    def __init__(
        self,
        *,
        client_label: str = "",
        runner: CommandRunner | None = None,
        remote_host_backoff: RemoteHostBackoff | None = None,
    ) -> None:
        super().__init__(
            "https://api.github.com",
            "",
            platform_mode="github",
            client_label=client_label,
            remote_host_backoff=remote_host_backoff,
        )
        self._runner = runner or SubprocessCommandRunner()
    def get(self, path: str, headers: dict[str, str] | None = None, *, repo: str | None = None, **params: Any) -> Any:
        """Read a GitHub API resource through ``gh api``."""
        del headers, repo
        return json.loads(self._run("GET", path, params=params))

    def get_raw(self, path: str, headers: dict[str, str] | None = None, *, repo: str | None = None) -> str:
        """Read raw response text through ``gh api``."""
        del repo
        return self._run("GET", path, params={}, headers=headers)

    def post(self, path: str, body: dict[str, Any], *, repo: str | None = None) -> dict[str, Any]:
        """Write a JSON resource through ``gh api``."""
        del repo
        return json.loads(self._run("POST", path, body=body))

    def is_capability_available(self, repo: str) -> bool:
        """Treat the authenticated gh session as the capability boundary."""
        del repo
        return True

    def _run(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> str:
        query = urlencode(params or {}, doseq=True)
        endpoint = f"{path}?{query}" if query else path
        command = ["gh", "api", endpoint, "--method", method]
        for name, value in (headers or {}).items():
            command.extend(["--header", f"{name}: {value}"])
        input_text = None
        if body is not None:
            command.extend(["--input", "-"])
            input_text = json.dumps(body)
        return self._run_remote_command(self._runner, command, input_text)
