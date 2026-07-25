"""HttpsCloneUrlResolver — builds HTTPS clone URLs."""

from pr_auto_reviewer.application.ports.outbound.clone_url_resolver_port import (
    CloneUrlResolverPort,
)

_HTTPS_TEMPLATES: dict[str, str] = {
    "codeberg": "https://codeberg.org/{repo}.git",
    "github": "https://github.com/{repo}.git",
}


class HttpsCloneUrlResolver(CloneUrlResolverPort):
    """Produces standard HTTPS clone URLs for Forgejo/Codeberg and GitHub."""

    def __init__(self, platform_mode: str) -> None:
        self._platform_mode: str = platform_mode

    def resolve(self, repository: str) -> str:
        """Build an HTTPS clone URL for the configured platform."""
        template = _HTTPS_TEMPLATES.get(self._platform_mode)
        if template is None:
            raise ValueError(
                f"Unknown platform mode: {self._platform_mode!r}"
            )
        return template.format(repo=repository)
