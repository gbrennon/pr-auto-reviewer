from __future__ import annotations

from typing import Any

from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)


class FakeGitPlatformHttpClient(GitPlatformHttpClient):

    def __init__(self, paths: dict[str, Any] | None = None) -> None:
        super().__init__("http://stub", "stub-token")
        self._paths: dict[str, Any] = paths or {}

    def get(self, path: str, **params: Any) -> Any:
        result = self._paths.get(path)
        if result is None:
            raise KeyError(f"No fake data for {path}")
        if isinstance(result, Exception):
            raise result
        return result

    def get_raw(self, path: str) -> str:
        return str(self.get(path) or "")

    def post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        return self.get(path)
