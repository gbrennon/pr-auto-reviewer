"""Behavioral tests for SshCloneUrlResolver."""

import pytest

from pr_auto_reviewer.infrastructure.clone_url_resolvers.ssh_clone_url_resolver import (
    SshCloneUrlResolver,
)


class TestSshCloneUrlResolver:
    """Exercises SshCloneUrlResolver across platform modes."""

    def test_resolve_when_codeberg_then_returns_codeberg_url(self) -> None:
        assert (
            SshCloneUrlResolver("codeberg").resolve("o/r")
            == "git@codeberg.org:o/r.git"
        )

    def test_resolve_when_github_then_returns_github_url(self) -> None:
        assert (
            SshCloneUrlResolver("github").resolve("o/r")
            == "git@github.com:o/r.git"
        )

    def test_resolve_when_forgejo_then_returns_codeberg_url(self) -> None:
        assert (
            SshCloneUrlResolver("forgejo").resolve("o/r")
            == "git@codeberg.org:o/r.git"
        )

    def test_resolve_when_unknown_mode_then_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            SshCloneUrlResolver("gitlab").resolve("o/r")