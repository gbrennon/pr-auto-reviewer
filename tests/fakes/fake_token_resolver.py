"""Fake TokenResolver for tracking calls in tests."""

from __future__ import annotations


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