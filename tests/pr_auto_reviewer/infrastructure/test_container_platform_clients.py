"""Behavior tests for wire_platform_clients() — verifies PlatformClients
dataclass is populated correctly for each platform-mode + output-mode combination."""

from __future__ import annotations

import pytest

from pr_auto_reviewer.infrastructure.config import Config
from pr_auto_reviewer.infrastructure.container._platform_clients import (
    PlatformClients,
    wire_platform_clients,
)
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.infrastructure.client.token_resolver import TokenResolver
from pr_auto_reviewer.infrastructure.client.preflight.requests_http_client import (
    RequestsHttpClient,
)
from pr_auto_reviewer.infrastructure.client.preflight.preflight_verifier import (
    PreflightVerifier,
)
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider
from pr_auto_reviewer.infrastructure.token_verifier import TokenVerifier

from pr_auto_reviewer.infrastructure.config.org_token_overrides import (
    OrgTokenOverrides,
)
from pr_auto_reviewer.infrastructure.config.org_token_entry import (
    OrgTokenEntry,
)

# ── defaults for every config value not being varied ──────────────────────
DEFAULT_FORGEJO = dict(
    forgejo_owner_token="fj-own",
    forgejo_reviewer_token="fj-rev",
    forgejo_reviewer_username="fj-bot",
)
DEFAULT_GITHUB = dict(
    github_owner_token="gh-own",
    github_reviewer_token="gh-rev",
    github_reviewer_username="gh-bot",
)


class TestWirePlatformClients:
    """Behaviour of wire_platform_clients(config) -> PlatformClients."""

    # ── single-platform: forgejo ──────────────────────────────────────────

    @pytest.fixture
    def forgejo_config(self) -> Config:
        return Config(
            env="test",
            platform_mode=GitProvider.FORGEJO,
            **DEFAULT_FORGEJO,
        )

    def test_forgejo_returns_platform_clients(self, forgejo_config: Config) -> None:
        result = wire_platform_clients(forgejo_config)

        assert isinstance(result, PlatformClients)

    def test_forgejo_http_client_is_git_platform_client(
        self,
        forgejo_config: Config,
    ) -> None:
        result = wire_platform_clients(forgejo_config)

        assert isinstance(result.http_client, GitPlatformHttpClient)

    def test_forgejo_reviewer_client_is_different_instance(
        self,
        forgejo_config: Config,
    ) -> None:
        result = wire_platform_clients(forgejo_config)

        assert isinstance(result.reviewer_client, GitPlatformHttpClient)
        assert result.reviewer_client is not result.http_client

    def test_forgejo_clients_have_correct_api_url(
        self,
        forgejo_config: Config,
    ) -> None:
        result = wire_platform_clients(forgejo_config)

        assert result.http_client.base_url == "https://codeberg.org/api/v1"
        assert result.reviewer_client.base_url == "https://codeberg.org/api/v1"
        assert result.http_client._platform_mode == "forgejo"
        assert result.reviewer_client._platform_mode == "forgejo"

    def test_forgejo_clients_use_owner_token_for_http_client(
        self,
        forgejo_config: Config,
    ) -> None:
        result = wire_platform_clients(forgejo_config)

        assert result.http_client._token == "fj-own"
        assert result.http_client._role == "owner"

    def test_forgejo_clients_use_reviewer_token_for_reviewer_client(
        self,
        forgejo_config: Config,
    ) -> None:
        result = wire_platform_clients(forgejo_config)

        assert result.reviewer_client._token == "fj-rev"
        assert result.reviewer_client._role == "reviewer"

    def test_forgejo_reviewer_token_falls_back_to_owner_when_missing(self) -> None:
        config = Config(
            env="test",
            platform_mode=GitProvider.FORGEJO,
            forgejo_owner_token="fj-own",
            forgejo_reviewer_token="",
            forgejo_reviewer_username="",
        )

        result = wire_platform_clients(config)

        assert result.reviewer_client._token == "fj-own"

    def test_forgejo_clients_have_token_resolver_with_forgejo_prefix(
        self,
        forgejo_config: Config,
    ) -> None:
        result = wire_platform_clients(forgejo_config)

        assert isinstance(result.http_client._token_resolver, TokenResolver)
        _token, source = result.http_client._token_resolver.resolve_source(
            "OWNER",
            "test-org/repo",
        )
        assert source.startswith("FORGEJO_")
        reviewer_token = result.http_client._token_resolver.resolve(
            "reviewer",
            "test-org/repo",
        )
        assert reviewer_token == "fj-rev"

    def test_forgejo_clients_share_same_token_resolver(
        self,
        forgejo_config: Config,
    ) -> None:
        result = wire_platform_clients(forgejo_config)

        assert (
            result.http_client._token_resolver is result.reviewer_client._token_resolver
        )

    def test_forgejo_clients_have_forgejo_auth_headers_preflight(
        self,
        forgejo_config: Config,
    ) -> None:
        result = wire_platform_clients(forgejo_config)

        pv = result.http_client._preflight_verifier
        assert isinstance(pv, PreflightVerifier)
        assert pv._platform == "forgejo"

    def test_forgejo_preflight_uses_forgejo_api_url_http_client(
        self,
        forgejo_config: Config,
    ) -> None:
        result = wire_platform_clients(forgejo_config)

        pv = result.http_client._preflight_verifier
        assert isinstance(pv._http, RequestsHttpClient)
        assert pv._http._base_url == "https://codeberg.org/api/v1"

    def test_forgejo_token_verifier_is_token_verifier_instance(
        self,
        forgejo_config: Config,
    ) -> None:
        result = wire_platform_clients(forgejo_config)

        assert isinstance(result.token_verifier, TokenVerifier)

    def test_forgejo_no_dual_platform_fields(self, forgejo_config: Config) -> None:
        result = wire_platform_clients(forgejo_config)

        assert result.forgejo_owner is None
        assert result.forgejo_reviewer is None

    # ── single-platform: github ───────────────────────────────────────────

    @pytest.fixture
    def github_config(self) -> Config:
        return Config(
            env="test",
            platform_mode=GitProvider.GITHUB,
            **DEFAULT_GITHUB,
        )

    def test_github_returns_platform_clients(self, github_config: Config) -> None:
        result = wire_platform_clients(github_config)

        assert isinstance(result, PlatformClients)

    def test_github_clients_have_correct_api_url(
        self,
        github_config: Config,
    ) -> None:
        result = wire_platform_clients(github_config)

        assert result.http_client.base_url == "https://api.github.com"
        assert result.reviewer_client.base_url == "https://api.github.com"
        assert result.http_client._platform_mode == "github"
        assert result.reviewer_client._platform_mode == "github"

    def test_github_token_resolver_uses_github_prefix(
        self,
        github_config: Config,
    ) -> None:
        result = wire_platform_clients(github_config)

        _token, source = result.http_client._token_resolver.resolve_source(
            "OWNER",
            "test-org/repo",
        )
        assert source.startswith("GITHUB_")
        reviewer_token = result.http_client._token_resolver.resolve(
            "reviewer",
            "test-org/repo",
        )
        assert reviewer_token == "gh-rev"

    def test_github_preflight_uses_github_auth_headers(
        self,
        github_config: Config,
    ) -> None:
        result = wire_platform_clients(github_config)

        pv = result.http_client._preflight_verifier
        assert pv._platform == "github"

    def test_github_reviewer_token_falls_back_to_owner_when_missing(self) -> None:
        config = Config(
            env="test",
            platform_mode=GitProvider.GITHUB,
            github_owner_token="gh-own",
            github_reviewer_token="",
            github_reviewer_username="",
        )

        result = wire_platform_clients(config)

        assert result.reviewer_client._token == "gh-own"

    def test_github_no_dual_platform_fields(self, github_config: Config) -> None:
        result = wire_platform_clients(github_config)

        assert result.forgejo_owner is None
        assert result.forgejo_reviewer is None

    def test_github_http_client_is_git_platform_client(
        self,
        github_config: Config,
    ) -> None:
        result = wire_platform_clients(github_config)

        assert isinstance(result.http_client, GitPlatformHttpClient)

    def test_github_reviewer_client_is_different_instance(
        self,
        github_config: Config,
    ) -> None:
        result = wire_platform_clients(github_config)

        assert isinstance(result.reviewer_client, GitPlatformHttpClient)
        assert result.reviewer_client is not result.http_client

    def test_github_clients_use_owner_token_for_http_client(
        self,
        github_config: Config,
    ) -> None:
        result = wire_platform_clients(github_config)

        assert result.http_client._token == "gh-own"
        assert result.http_client._role == "owner"

    def test_github_clients_use_reviewer_token_for_reviewer_client(
        self,
        github_config: Config,
    ) -> None:
        result = wire_platform_clients(github_config)

        assert result.reviewer_client._token == "gh-rev"
        assert result.reviewer_client._role == "reviewer"

    def test_github_clients_share_same_token_resolver(
        self,
        github_config: Config,
    ) -> None:
        result = wire_platform_clients(github_config)

        assert (
            result.http_client._token_resolver is result.reviewer_client._token_resolver
        )

    def test_github_preflight_uses_github_api_url_http_client(
        self,
        github_config: Config,
    ) -> None:
        result = wire_platform_clients(github_config)

        pv = result.http_client._preflight_verifier
        assert isinstance(pv._http, RequestsHttpClient)
        assert pv._http._base_url == "https://api.github.com"

    def test_github_token_verifier_is_token_verifier_instance(
        self,
        github_config: Config,
    ) -> None:
        result = wire_platform_clients(github_config)

        assert isinstance(result.token_verifier, TokenVerifier)

    # ── BOTH mode ─────────────────────────────────────────────────────────

    @pytest.fixture
    def both_config(self) -> Config:
        return Config(
            env="test",
            platform_mode=GitProvider.BOTH,
            github_owner_token="gh-own",
            github_reviewer_token="gh-rev",
            github_reviewer_username="gh-bot",
            forgejo_owner_token="fj-own",
            forgejo_reviewer_token="fj-rev",
            forgejo_reviewer_username="fj-bot",
        )

    def test_both_http_client_is_github_owner(self, both_config: Config) -> None:
        result = wire_platform_clients(both_config)

        assert result.http_client.base_url == "https://api.github.com"
        assert result.http_client._token == "gh-own"
        assert result.http_client._platform_mode == "github"
        assert result.http_client._role == "owner"
        assert result.http_client._preflight_verifier._platform == "github"

    def test_both_reviewer_client_is_github_reviewer(
        self,
        both_config: Config,
    ) -> None:
        result = wire_platform_clients(both_config)

        assert result.reviewer_client.base_url == "https://api.github.com"
        assert result.reviewer_client._token == "gh-rev"
        assert result.reviewer_client._platform_mode == "github"
        assert result.reviewer_client._role == "reviewer"

    def test_both_forgejo_owner_is_present(self, both_config: Config) -> None:
        result = wire_platform_clients(both_config)

        assert isinstance(result.forgejo_owner, GitPlatformHttpClient)
        assert result.forgejo_owner.base_url == "https://codeberg.org/api/v1"
        assert result.forgejo_owner._token == "fj-own"
        assert result.forgejo_owner._platform_mode == "forgejo"
        assert result.forgejo_owner._role == "owner"
        assert result.forgejo_owner._preflight_verifier._platform == "forgejo"

    def test_both_forgejo_reviewer_is_present(self, both_config: Config) -> None:
        result = wire_platform_clients(both_config)

        assert isinstance(result.forgejo_reviewer, GitPlatformHttpClient)
        assert result.forgejo_reviewer.base_url == "https://codeberg.org/api/v1"
        assert result.forgejo_reviewer._token == "fj-rev"
        assert result.forgejo_reviewer._platform_mode == "forgejo"
        assert result.forgejo_reviewer._role == "reviewer"

    def test_both_github_clients_use_different_resolver_from_forgejo(
        self,
        both_config: Config,
    ) -> None:
        result = wire_platform_clients(both_config)

        gh_resolver = result.http_client._token_resolver
        fj_resolver = result.forgejo_owner._token_resolver
        assert gh_resolver is not fj_resolver
        assert result.reviewer_client._token_resolver is gh_resolver
        assert result.forgejo_reviewer._token_resolver is fj_resolver

    def test_both_github_resolver_has_github_prefix(
        self,
        both_config: Config,
    ) -> None:
        result = wire_platform_clients(both_config)

        _token, source = result.http_client._token_resolver.resolve_source(
            "OWNER",
            "test-org/repo",
        )
        assert source.startswith("GITHUB_")
        reviewer_token = result.http_client._token_resolver.resolve(
            "reviewer",
            "test-org/repo",
        )
        assert reviewer_token == "gh-rev"

    def test_both_forgejo_resolver_has_forgejo_prefix(
        self,
        both_config: Config,
    ) -> None:
        result = wire_platform_clients(both_config)

        assert result.forgejo_owner is not None
        _token, source = result.forgejo_owner._token_resolver.resolve_source(
            "OWNER",
            "test-org/repo",
        )
        assert source.startswith("FORGEJO_")
        reviewer_token = result.forgejo_owner._token_resolver.resolve(
            "reviewer",
            "test-org/repo",
        )
        assert reviewer_token == "fj-rev"

    # ── terminal mode ─────────────────────────────────────────────────────

    @pytest.mark.parametrize(
        "platform_mode",
        [
            GitProvider.FORGEJO,
            GitProvider.GITHUB,
            GitProvider.BOTH,
        ],
    )
    def test_terminal_mode_token_verifier_has_persist_false(
        self,
        platform_mode: GitProvider,
    ) -> None:
        config = Config(
            env="test",
            platform_mode=platform_mode,
            forgejo_owner_token="fj-own",
            github_owner_token="gh-own",
            output_mode="terminal",
        )

        result = wire_platform_clients(config)

        assert result.token_verifier._persist is False

    @pytest.mark.parametrize(
        "platform_mode,output_mode",
        [
            (GitProvider.FORGEJO, "forgejo"),
            (GitProvider.GITHUB, "github"),
            (GitProvider.BOTH, "both"),
        ],
    )
    def test_non_terminal_mode_token_verifier_has_persist_true(
        self,
        platform_mode: GitProvider,
        output_mode: str,
    ) -> None:
        config = Config(
            env="test",
            platform_mode=platform_mode,
            forgejo_owner_token="fj-own",
            github_owner_token="gh-own",
            output_mode=output_mode,
        )

        result = wire_platform_clients(config)

        assert result.token_verifier._persist is True

    def test_both_token_verifier_uses_owner_and_reviewer_clients(
        self,
        both_config: Config,
    ) -> None:
        result = wire_platform_clients(both_config)

        assert result.token_verifier._owner_client is result.http_client
        assert result.token_verifier._reviewer_client is result.reviewer_client

    # ── org token overrides ───────────────────────────────────────────────

    def test_org_token_overrides_are_passed_to_token_resolver(self) -> None:
        overrides = OrgTokenOverrides(
            forgejo={"my-org": OrgTokenEntry(owner_token="custom-token")},
        )
        config = Config(
            env="test",
            platform_mode=GitProvider.FORGEJO,
            forgejo_owner_token="fj-own",
            org_token_overrides=overrides,
        )

        result = wire_platform_clients(config)

        assert result.http_client._token_resolver._overrides is overrides
        assert (
            result.http_client._token_resolver.resolve("owner", "my-org/repo")
            == "custom-token"
        )

    # ── custom API URLs ───────────────────────────────────────────────────

    def test_custom_github_api_url_is_respected(self) -> None:
        config = Config(
            env="test",
            platform_mode=GitProvider.GITHUB,
            github_api_url="https://git.internal.example.com/api",
            github_owner_token="gh-own",
        )

        result = wire_platform_clients(config)

        assert result.http_client.base_url == "https://git.internal.example.com/api"

    def test_custom_forgejo_api_url_is_respected(self) -> None:
        config = Config(
            env="test",
            platform_mode=GitProvider.FORGEJO,
            forgejo_api_url="https://git.internal.example.com/api/v1",
            forgejo_owner_token="fj-own",
        )

        result = wire_platform_clients(config)

        assert result.http_client.base_url == "https://git.internal.example.com/api/v1"

    def test_both_custom_api_urls_are_respected(self) -> None:
        config = Config(
            env="test",
            platform_mode=GitProvider.BOTH,
            github_api_url="https://git.internal.example.com/gh-api",
            forgejo_api_url="https://git.internal.example.com/fj-api/v1",
            github_owner_token="gh-own",
            forgejo_owner_token="fj-own",
        )

        result = wire_platform_clients(config)

        assert result.http_client.base_url == "https://git.internal.example.com/gh-api"
        assert result.forgejo_owner is not None
        assert (
            result.forgejo_owner.base_url
            == "https://git.internal.example.com/fj-api/v1"
        )
        assert (
            result.reviewer_client.base_url == "https://git.internal.example.com/gh-api"
        )
        assert result.forgejo_reviewer is not None
        assert (
            result.forgejo_reviewer.base_url
            == "https://git.internal.example.com/fj-api/v1"
        )
