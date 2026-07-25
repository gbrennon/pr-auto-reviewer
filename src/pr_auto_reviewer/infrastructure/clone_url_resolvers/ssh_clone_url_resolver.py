"""SshCloneUrlResolver — builds SSH clone URLs."""

from pr_auto_reviewer.application.ports.outbound.clone_url_resolver_port import (
    CloneUrlResolverPort,
)

_SSH_TEMPLATES: dict[str, str] = {
    "codeberg": "git@codeberg.org:{repo}.git",
    "github": "git@github.com:{repo}.git",
}


class SshCloneUrlResolver(CloneUrlResolverPort):
    """Produces SSH clone URLs for Forgejo/Codeberg and GitHub."""

    def __init__(self, platform_mode: str) -> None:
        self._platform_mode: str = platform_mode

    def resolve(self, repository: str) -> str:
        """Build an SSH clone URL for the configured platform."""
        template = _SSH_TEMPLATES.get(self._platform_mode)
        if template is None:
            raise ValueError(
                f"Unknown platform mode: {self._platform_mode!r}"
            )
        return template.format(repo=repository)
