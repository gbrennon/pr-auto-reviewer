import os
import time
from pathlib import Path

import pytest

from pr_auto_reviewer.domain.entities.api_access_capability import (
    ApiAccessCapability,
)
from pr_auto_reviewer.domain.exceptions.api_access_capability_suspended_error import (
    ApiAccessCapabilitySuspendedError,
)
from pr_auto_reviewer.domain.value_objects.capability_suspension import (
    CapabilitySuspension,
)
from pr_auto_reviewer.infrastructure.client.api_access_capability_state import (
    ApiAccessCapabilityState,
)
from pr_auto_reviewer.infrastructure.client.api_access_capability_store import (
    ApiAccessCapabilityStore,
)
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.infrastructure.client.token_resolver import (
    TokenDefaults,
    TokenResolver,
)


class Response:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, str]:
        return {"ok": "yes"}

    @property
    def text(self) -> str:
        return ""


class TestApiAccessCapabilityHttp:
    def test_suspended_capability_makes_no_http_request(self, tmp_path: Path, monkeypatch):
        state = ApiAccessCapabilityState(ApiAccessCapabilityStore(tmp_path / "state.json"))
        client = GitPlatformHttpClient(
            "https://api.example.com",
            "default-token",
            client_label="owner",
            platform_mode="github",
            capability_state=state,
        )
        state.suspend(
            ApiAccessCapability(
                platform="github",
                role="owner",
                source_name="GITHUB_OWNER_TOKEN",
                scope="acme/widgets",
            ),
            CapabilitySuspension(
                suspended_until=time.time() + 600,
                resource="core",
                remaining=0,
                limit=5_000,
                reason="rate_limit_exhausted",
            ),
        )
        calls: list[str] = []
        monkeypatch.setattr(
            "pr_auto_reviewer.infrastructure.client.git_platform_http_client.requests.get",
            lambda *args, **kwargs: calls.append(args[0]),
        )

        with pytest.raises(ApiAccessCapabilitySuspendedError):
            client.get("/repos", repo="acme/widgets")

        assert calls == []

    def test_rate_limit_freezes_resolved_override_source(self, tmp_path: Path, monkeypatch):
        source_name = "GITHUB_TOKEN_acme_OWNER"
        os.environ[source_name] = "org-token"
        try:
            resolver = TokenResolver(
                "GITHUB",
                TokenDefaults(owner_token="default-token"),
            )
            state = ApiAccessCapabilityState(
                ApiAccessCapabilityStore(tmp_path / "state.json")
            )
            client = GitPlatformHttpClient(
                "https://api.example.com",
                "default-token",
                client_label="owner",
                platform_mode="github",
                token_resolver=resolver,
                capability_state=state,
            )
            monkeypatch.setattr(
                "pr_auto_reviewer.infrastructure.client.git_platform_http_client.requests.get",
                lambda *args, **kwargs: Response(
                    {
                        "x-ratelimit-limit": "5000",
                        "x-ratelimit-remaining": "0",
                        "x-ratelimit-reset": "1600000600",
                        "x-ratelimit-resource": "core",
                    }
                ),
            )

            client.get("/repos", repo="acme/widgets")

            assert state.is_available("github", "owner", source_name, "acme/widgets") is False
            assert state.is_available(
                "github", "owner", "GITHUB_OWNER_TOKEN", "other/repo"
            ) is True
        finally:
            del os.environ[source_name]
