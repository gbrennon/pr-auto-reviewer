"""Tests for SshCloneUrlResolver using fake."""

from __future__ import annotations

import pytest

from tests.fakes.fake_ssh_clone_url_resolver import FakeSshCloneUrlResolver


class TestFakeSshCloneUrlResolver:
    """Tests using the fake SshCloneUrlResolver."""

    def test_fake_can_be_instantiated(self) -> None:
        """Fake SSH clone URL resolver can be instantiated."""
        fake = FakeSshCloneUrlResolver()
        assert fake is not None

    def test_fake_resolve(self) -> None:
        """Fake resolve returns configured URL without SSH calls."""
        fake = FakeSshCloneUrlResolver()
        result = fake.resolve("git@github.com:owner/repo.git")
        assert result == "git@github.com:owner/repo.git"
        assert len(fake.resolve_calls) == 1