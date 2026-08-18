"""Tests for RepoUpdateTracker using fake."""

from __future__ import annotations

import pytest

from tests.fakes.fake_repo_update_tracker import FakeRepoUpdateTracker


class TestFakeRepoUpdateTracker:
    """Tests using the fake RepoUpdateTracker."""

    def test_fake_can_be_instantiated(self) -> None:
        """Fake repo update tracker can be instantiated."""
        fake = FakeRepoUpdateTracker()
        assert fake is not None

    def test_fake_is_stale_default(self) -> None:
        """Fake is_stale returns True by default."""
        fake = FakeRepoUpdateTracker()
        assert fake.is_stale("owner/repo", None) is True

    def test_fake_is_stale_new_repo(self) -> None:
        """Fake is_stale returns True for new repo."""
        fake = FakeRepoUpdateTracker()
        assert fake.is_stale("owner/repo", "abc") is True

    def test_fake_is_stale_cached(self) -> None:
        """Fake is_stale returns False when cached."""
        fake = FakeRepoUpdateTracker()
        fake._data["owner/repo"] = "abc"
        assert fake.is_stale("owner/repo", "abc") is False

    def test_fake_mark_seen(self) -> None:
        """Fake mark_seen tracks calls."""
        fake = FakeRepoUpdateTracker()
        fake.mark_seen("owner/repo", "abc123")
        assert len(fake.mark_seen_calls) == 1
        assert fake.mark_seen_calls[0] == ("owner/repo", "abc123")