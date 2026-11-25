"""Tests for selecting the Forgejo CLI transport."""

from pr_auto_reviewer.infrastructure.config import Config
from pr_auto_reviewer.infrastructure.container._platform_clients import (
    wire_platform_clients,
)
from pr_auto_reviewer.infrastructure.forgejo.fj_cli_client import FjCliClient
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider


class TestFjCliWiring:
    """Verify Forgejo CLI selection preserves existing client contracts."""

    def test_forgejo_cli_transport_uses_authenticated_cli_clients(self) -> None:
        config = Config(
            env="test",
            platform_mode=GitProvider.FORGEJO,
            platform_transport="cli",
        )

        clients = wire_platform_clients(config)

        assert isinstance(clients.http_client, FjCliClient)
        assert isinstance(clients.reviewer_client, FjCliClient)
