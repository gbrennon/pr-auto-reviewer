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
        *,
        token: str,
        org: str,
        repo: str,
        pr_number: int,
        role: str,
    ) -> None:
        self.calls.append(
            {
                "token": token,
                "org": org,
                "repo": repo,
                "pr_number": pr_number,
                "role": role,
            }
        )
        if self.should_fail:
            raise PreflightVerificationError(
                platform="test", org=org, role=role, http_status=403, step="auth",
            )


class FakeTokenResolver:
    """Lightweight fake TokenResolver for tracking calls in tests."""

    def __init__(self, token_map: dict[str, str] | None = None) -> None:
        self._map: dict[str, str] = token_map or {}
        self.calls: list[dict[str, str]] = []

    def resolve(self, role: str, repo: str) -> str:
        self.calls.append({"role": role, "repo": repo})
        return self._map.get(repo, "")
