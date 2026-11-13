from dataclasses import FrozenInstanceError

import pytest

from pr_auto_reviewer.domain.entities.api_access_capability import (
    ApiAccessCapability,
)
from pr_auto_reviewer.domain.entities.api_access_capability_registry import (
    ApiAccessCapabilityRegistry,
)
from pr_auto_reviewer.domain.value_objects.capability_suspension import (
    CapabilitySuspension,
)


class TestApiAccessCapabilityRegistry:
    def test_registers_capability_without_exposing_token_value(self):
        capability = ApiAccessCapability(
            platform="github",
            role="reviewer",
            source_name="GITHUB_TOKEN_acme_REVIEWER",
            scope="acme/widgets",
        )

        registry = ApiAccessCapabilityRegistry.empty().register(capability)

        assert registry.capabilities == (capability,)
        assert not hasattr(capability, "token")

    def test_suspends_capability_until_reset_time(self):
        capability = ApiAccessCapability(
            platform="github",
            role="reviewer",
            source_name="GITHUB_TOKEN_acme_REVIEWER",
            scope="acme/widgets",
        )
        suspension = CapabilitySuspension(
            suspended_until=1_600_000_600,
            resource="core",
            remaining=0,
            limit=5_000,
            reason="rate_limit_exhausted",
        )
        registry = ApiAccessCapabilityRegistry.empty().register(capability)

        suspended = registry.suspend(capability, suspension)

        assert suspended.is_available(capability, now=1_600_000_000) is False
        assert suspended.is_available(capability, now=1_600_000_600) is True

    def test_suspension_applies_to_same_key_across_repository_scopes(self):
        first_scope = ApiAccessCapability(
            platform="github",
            role="owner",
            source_name="GITHUB_OWNER_TOKEN",
            scope="acme/widgets",
        )
        second_scope = ApiAccessCapability(
            platform="github",
            role="owner",
            source_name="GITHUB_OWNER_TOKEN",
            scope="acme/gadgets",
        )
        suspension = CapabilitySuspension(
            suspended_until=1_600_000_600,
            resource="core",
            remaining=0,
            limit=5_000,
            reason="rate_limit_exhausted",
        )
        registry = ApiAccessCapabilityRegistry.empty()
        registry = registry.register(first_scope).register(second_scope)

        suspended = registry.suspend(first_scope, suspension)

        assert suspended.is_available(second_scope, now=1_600_000_000) is False

    def test_expired_suspension_is_available(self):
        capability = ApiAccessCapability(
            platform="forgejo",
            role="owner",
            source_name="FORGEJO_OWNER_TOKEN",
            scope="acme/widgets",
        )
        suspension = CapabilitySuspension(
            suspended_until=1_600_000_600,
            resource="core",
            remaining=0,
            limit=5_000,
            reason="rate_limit_exhausted",
        )
        registry = ApiAccessCapabilityRegistry.empty().register(capability)

        suspended = registry.suspend(capability, suspension)

        assert suspended.is_available(capability, now=1_600_000_601) is True

    def test_domain_objects_are_immutable(self):
        capability = ApiAccessCapability(
            platform="github",
            role="owner",
            source_name="GITHUB_OWNER_TOKEN",
            scope="acme/widgets",
        )

        with pytest.raises(FrozenInstanceError):
            capability.__setattr__("role", "reviewer")
