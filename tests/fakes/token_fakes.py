"""Fake TokenResolver and PreflightVerifier for HTTP client token tests."""

from __future__ import annotations

from typing import Any

from pr_auto_reviewer.domain.exceptions.preflight_verification_error import (
    PreflightVerificationError,
)


class FakeVerifier:
    """Lightweight fake PreflightVerifier that records calls and optionally
    raises ``PreflightVerificationError``."""

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[dict[str, Any]] = []

    def verify(
        self,
        token: str,
        org: str,
        repo: str,
        pr_number: int,
        role: str = "owner",
        token_source: str = "",
    ) -> None:
        self.calls.append(
            {
                "token": token,
                "org": org,
                "repo": repo,
                "pr_number": pr_number,
                "role": role,
                "token_source": token_source,
            }
        )
        if self.should_fail:
            raise PreflightVerificationError(
                platform="test", org=org, role=role, http_status=403, step="auth",
                token_source=token_source, url=f"https://test/{repo}", method="GET",
            )


class FakeTokenResolver:
    """Lightweight fake TokenResolver for tracking calls in tests."""

    def __init__(self, token_map: dict[str, str] | None = None) -> None:
        self._map: dict[str, str] = token_map or {}
        self.calls: list[dict[str, str]] = []

    def resolve(self, role: str, repo: str) -> str:
        self.calls.append({"role": role, "repo": repo})
        return self._map.get(repo, "")

    def resolve_source(self, role: str, repo: str) -> tuple[str, str]:
        token = self.resolve(role, repo)
        return token, f"FAKE_TOKEN_{role.upper()}"

    def reviewer_username(self, repo: str) -> str:
        return "fake-reviewer-username"
