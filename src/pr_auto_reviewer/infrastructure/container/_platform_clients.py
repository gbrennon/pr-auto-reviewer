"""Platform clients wiring — TokenResolver, PreflightVerifier,
GitPlatformHttpClient, TokenVerifier instances."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from pr_auto_reviewer.infrastructure.config import Config
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.infrastructure.client.token_resolver import (
    TokenDefaults,
    TokenResolver,
)
from pr_auto_reviewer.infrastructure.client.preflight.forgejo_auth_headers import (
    ForgejoAuthHeaders,
)
from pr_auto_reviewer.infrastructure.client.preflight.github_auth_headers import (
    GitHubAuthHeaders,
)
from pr_auto_reviewer.infrastructure.client.preflight.requests_http_client import (
    RequestsHttpClient,
)
from pr_auto_reviewer.infrastructure.client.preflight.preflight_verifier import (
    PreflightVerifier,
)
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider
from pr_auto_reviewer.infrastructure.token_verifier import TokenVerifier
from pr_auto_reviewer.application.ports.outbound.token_verifier_port import (
    TokenVerifierPort,
)


@dataclasses.dataclass
class PlatformClients:
    """Wired platform-client instances.

    In single-platform mode ``forgejo_owner`` and ``forgejo_reviewer``
    are ``None``.  ``http_client`` is always the *owner* client and
    ``reviewer_client`` the *reviewer* client for the primary platform
    (GitHub in BOTH mode, the configured platform in single mode).
    """

    http_client: GitPlatformHttpClient
    reviewer_client: GitPlatformHttpClient
    token_verifier: TokenVerifierPort
    forgejo_owner: GitPlatformHttpClient | None = None
    forgejo_reviewer: GitPlatformHttpClient | None = None


def wire_platform_clients(config: Config, *, _verified_cache_path: Path | None = None, _store_path: Path | None = None) -> PlatformClients:
    """Create all platform-client instances for *config*."""

    is_terminal = config.output_mode == "terminal"

    if config.platform_mode == GitProvider.BOTH:
        github_resolver = TokenResolver(
            "GITHUB",
            TokenDefaults(
                owner_token=config.github_owner_token,
                reviewer_token=config.github_reviewer_token,
                reviewer_username=config.github_reviewer_username,
            ),
            overrides=config.org_token_overrides,
        )
        forgejo_resolver = TokenResolver(
            "FORGEJO",
            TokenDefaults(
                owner_token=config.forgejo_owner_token,
                reviewer_token=config.forgejo_reviewer_token,
                reviewer_username=config.forgejo_reviewer_username,
            ),
            overrides=config.org_token_overrides,
        )

        github_preflight = PreflightVerifier(
            RequestsHttpClient(config.github_api_url),
            GitHubAuthHeaders(),
            config.github_api_url,
            "github",
        )
        forgejo_preflight = PreflightVerifier(
            RequestsHttpClient(config.forgejo_api_url),
            ForgejoAuthHeaders(),
            config.forgejo_api_url,
            "forgejo",
        )

        gb_owner = GitPlatformHttpClient(
            config.github_api_url,
            config.github_owner_token,
            platform_mode="github",
            client_label="owner",
            preflight_verifier=github_preflight,
            token_resolver=github_resolver,
            _verified_cache_path=_verified_cache_path,
        )
        gb_reviewer = GitPlatformHttpClient(
            config.github_api_url,
            config.github_reviewer_token,
            platform_mode="github",
            client_label="reviewer",
            preflight_verifier=github_preflight,
            token_resolver=github_resolver,
            _verified_cache_path=_verified_cache_path,
        )
        fj_owner = GitPlatformHttpClient(
            config.forgejo_api_url,
            config.forgejo_owner_token,
            platform_mode="forgejo",
            client_label="owner",
            preflight_verifier=forgejo_preflight,
            token_resolver=forgejo_resolver,
            _verified_cache_path=_verified_cache_path,
        )
        fj_reviewer = GitPlatformHttpClient(
            config.forgejo_api_url,
            config.forgejo_reviewer_token,
            platform_mode="forgejo",
            client_label="reviewer",
            preflight_verifier=forgejo_preflight,
            token_resolver=forgejo_resolver,
            _verified_cache_path=_verified_cache_path,
        )

        return PlatformClients(
            http_client=gb_owner,
            reviewer_client=gb_reviewer,
            token_verifier=TokenVerifier(
                gb_owner,
                gb_reviewer,
                persist=not is_terminal,
                forgejo_owner_client=fj_owner,
                forgejo_reviewer_client=fj_reviewer,
                _store_path=_store_path,
            ),
            forgejo_owner=fj_owner,
            forgejo_reviewer=fj_reviewer,
        )

    # --- single-platform mode -------------------------------------------------
    is_github = config.platform_mode == GitProvider.GITHUB
    api_url = (
        config.github_api_url if is_github else config.forgejo_api_url
    )
    owner_token = (
        config.github_owner_token
        if is_github
        else config.forgejo_owner_token
    )
    reviewer_token = (
        (config.github_reviewer_token or config.github_owner_token)
        if is_github
        else (
            config.forgejo_reviewer_token or config.forgejo_owner_token
        )
    )
    reviewer_username = (
        config.github_reviewer_username
        if is_github
        else config.forgejo_reviewer_username
    )
    platform_value = config.platform_mode.value

    resolver = TokenResolver(
        "GITHUB" if is_github else "FORGEJO",
        TokenDefaults(
            owner_token=owner_token,
            reviewer_token=reviewer_token,
            reviewer_username=reviewer_username,
        ),
        overrides=config.org_token_overrides,
    )

    preflight = PreflightVerifier(
        RequestsHttpClient(api_url),
        GitHubAuthHeaders() if is_github else ForgejoAuthHeaders(),
        api_url,
        "github" if is_github else "forgejo",
    )

    http_client = GitPlatformHttpClient(
        api_url,
        owner_token,
        platform_mode=platform_value,
        client_label="owner",
        preflight_verifier=preflight,
        token_resolver=resolver,
        _verified_cache_path=_verified_cache_path,
    )
    reviewer_client = GitPlatformHttpClient(
        api_url,
        reviewer_token,
        platform_mode=platform_value,
        client_label="reviewer",
        preflight_verifier=preflight,
        token_resolver=resolver,
        _verified_cache_path=_verified_cache_path,
    )

    return PlatformClients(
        http_client=http_client,
        reviewer_client=reviewer_client,
        token_verifier=TokenVerifier(
            http_client, reviewer_client, persist=not is_terminal,
            _store_path=_store_path,
        ),
    )
