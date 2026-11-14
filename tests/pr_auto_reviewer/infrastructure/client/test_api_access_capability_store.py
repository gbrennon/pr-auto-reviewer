import json
import time
from pathlib import Path

from pr_auto_reviewer.domain.entities.api_access_capability import (
    ApiAccessCapability,
)
from pr_auto_reviewer.domain.entities.api_access_capability_registry import (
    ApiAccessCapabilityRegistry,
)
from pr_auto_reviewer.domain.value_objects.capability_suspension import (
    CapabilitySuspension,
)
from pr_auto_reviewer.infrastructure.client.api_access_capability_store import (
    ApiAccessCapabilityStore,
)


class TestApiAccessCapabilityStore:
    def test_round_trip_persists_capability_suspension(self, tmp_path: Path):
        store = ApiAccessCapabilityStore(tmp_path / "capabilities.json")
        capability = ApiAccessCapability(
            platform="github",
            role="reviewer",
            source_name="GITHUB_TOKEN_acme_REVIEWER",
            scope="acme/widgets",
        )
        registry = ApiAccessCapabilityRegistry.empty().register(capability).suspend(
            capability,
            CapabilitySuspension(
                suspended_until=time.time() + 600,
                resource="core",
                remaining=0,
                limit=5_000,
                reason="rate_limit_exhausted",
            ),
        )

        store.save(registry)
        loaded = store.load()

        assert loaded.capabilities[0].source_name == "GITHUB_TOKEN_acme_REVIEWER"
        assert loaded.capabilities[0].suspension is not None
        assert loaded.capabilities[0].suspension.suspended_until > time.time()

    def test_malformed_state_returns_empty_registry(self, tmp_path: Path):
        path = tmp_path / "capabilities.json"
        path.write_text("not json")
        store = ApiAccessCapabilityStore(path)

        loaded = store.load()

        assert loaded == ApiAccessCapabilityRegistry.empty()

    def test_expired_suspensions_are_not_loaded_as_active(self, tmp_path: Path):
        path = tmp_path / "capabilities.json"
        path.write_text(
            json.dumps(
                {
                    "capabilities": [
                        {
                            "platform": "github",
                            "role": "owner",
                            "source_name": "GITHUB_OWNER_TOKEN",
                            "scope": "acme/widgets",
                            "suspension": {
                                "suspended_until": 1,
                                "resource": "core",
                                "remaining": 0,
                                "limit": 5_000,
                                "reason": "rate_limit_exhausted",
                            },
                        }
                    ]
                }
            )
        )
        store = ApiAccessCapabilityStore(path)

        loaded = store.load(now=2)

        assert loaded.capabilities[0].suspension is None

    def test_saved_state_does_not_contain_token_values(self, tmp_path: Path):
        path = tmp_path / "capabilities.json"
        store = ApiAccessCapabilityStore(path)
        capability = ApiAccessCapability(
            platform="github",
            role="owner",
            source_name="GITHUB_OWNER_TOKEN",
            scope="acme/widgets",
        )

        store.save(ApiAccessCapabilityRegistry.empty().register(capability))

        assert "token-value" not in path.read_text()
