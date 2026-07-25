"""Fake clone URL resolver for LocalChangesetFetcher tests."""

from pr_auto_reviewer.application.ports.outbound.clone_url_resolver_port import (
    CloneUrlResolverPort,
)

_FAKE_URLS: dict[str, str] = {
    "codeberg": "https://codeberg.org/{repo}.git",
    "github": "https://github.com/{repo}.git",
}


class FakeCloneUrlResolver(CloneUrlResolverPort):
    """Fake resolver that mirrors HTTPS URL templates for tests."""

    def __init__(self, platform_mode: str) -> None:
        self._platform_mode = platform_mode

    def resolve(self, repository: str) -> str:
        return _FAKE_URLS[self._platform_mode].format(repo=repository)
