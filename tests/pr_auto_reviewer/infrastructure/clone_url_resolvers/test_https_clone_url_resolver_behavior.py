"""Behavioral tests for HttpsCloneUrlResolver."""

import pytest

from pr_auto_reviewer.infrastructure.clone_url_resolvers.https_clone_url_resolver import (
    HttpsCloneUrlResolver,
)


class TestHttpsCloneUrlResolver:
    """Exercises HttpsCloneUrlResolver across platform modes."""

    def test_resolve_when_codeberg_then_returns_codeberg_url(self) -> None:
        assert (
            HttpsCloneUrlResolver("codeberg").resolve("o/r")
            == "https://codeberg.org/o/r.git"
        )

    def test_resolve_when_github_then_returns_github_url(self) -> None:
        assert (
            HttpsCloneUrlResolver("github").resolve("o/r")
            == "https://github.com/o/r.git"
        )

    def test_resolve_when_forgejo_then_returns_codeberg_url(self) -> None:
        assert (
            HttpsCloneUrlResolver("forgejo").resolve("o/r")
            == "https://codeberg.org/o/r.git"
        )

    def test_resolve_when_unknown_mode_then_raises_value_error(self) -> None:
        with pytest.raises(ValueError):
            HttpsCloneUrlResolver("gitlab").resolve("o/r")