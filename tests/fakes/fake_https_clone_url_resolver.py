"""Fake HttpsCloneUrlResolver for tests."""

from __future__ import annotations


class FakeHttpsCloneUrlResolver:
    """Fake HttpsCloneUrlResolver that returns pre-configured URLs."""

    def __init__(self, resolve_result: str = "https://github.com/owner/repo.git") -> None:
        self.resolve_result = resolve_result
        self.resolve_calls: list[tuple[str]] = []

    def resolve(self, url: str) -> str:
        """Return fake resolved URL without actual HTTP calls."""
        self.resolve_calls.append((url,))
        return self.resolve_result