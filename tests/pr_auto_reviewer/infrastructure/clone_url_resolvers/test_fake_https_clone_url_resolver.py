"""Tests for HttpsCloneUrlResolver using fake."""

from __future__ import annotations

import pytest

from tests.fakes.fake_https_clone_url_resolver import FakeHttpsCloneUrlResolver


class TestFakeHttpsCloneUrlResolver:
    """Tests using the fake HttpsCloneUrlResolver."""

    def test_fake_can_be_instantiated(self) -> None:
        """Fake HTTPS clone URL resolver can be instantiated."""
        fake = FakeHttpsCloneUrlResolver()
        assert fake is not None

    def test_fake_resolve(self) -> None:
        """Fake resolve returns configured URL without HTTP calls."""
        fake = FakeHttpsCloneUrlResolver()
        result = fake.resolve("git@github.com:owner/repo.git")
        assert result == "https://github.com/owner/repo.git"
        assert len(fake.resolve_calls) == 1