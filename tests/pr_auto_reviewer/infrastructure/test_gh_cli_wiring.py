"""Tests for selecting the GitHub CLI transport."""

from pr_auto_reviewer.infrastructure.config import Config
from pr_auto_reviewer.infrastructure.container._platform_clients import (
    wire_platform_clients,
)
from pr_auto_reviewer.infrastructure.github.gh_cli_client import GhCliClient
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider


class TestGhCliWiring:
    """Verify CLI transport selection leaves application ports unchanged."""

    def test_github_cli_transport_uses_authenticated_cli_clients(self) -> None:
        config = Config(
            env="test",
            platform_mode=GitProvider.GITHUB,
            platform_transport="cli",
        )

        clients = wire_platform_clients(config)

        assert isinstance(clients.http_client, GhCliClient)
        assert isinstance(clients.reviewer_client, GhCliClient)
