from ._helpers import *


class TestTokenResolverForgejoPrefix:
    def test_resolve_returns_forgejo_org_override_owner(self):
        resolver = _resolver(
            platform_prefix="FORGEJO", FORGEJO_TOKEN_myorg_OWNER="fj-own"
        )
        assert resolver.resolve("OWNER", "myorg/repo") == "fj-own"

    def test_resolve_returns_forgejo_org_override_reviewer(self):
        resolver = _resolver(
            platform_prefix="FORGEJO", FORGEJO_TOKEN_myorg_REVIEWER="fj-rev"
        )
        assert resolver.resolve("REVIEWER", "myorg/repo") == "fj-rev"

    def test_reviewer_username_returns_forgejo_org_override(self):
        resolver = _resolver(
            platform_prefix="FORGEJO",
            FORGEJO_TOKEN_myorg_REVIEWER_USERNAME="fj-user",
        )
        assert resolver.reviewer_username("myorg/repo") == "fj-user"

    def test_github_and_forgejo_prefixes_are_independent(self):
        gh = _resolver(GITHUB_TOKEN_myorg_OWNER="gh-tok")
        fj = _resolver(platform_prefix="FORGEJO", FORGEJO_TOKEN_myorg_OWNER="fj-tok")
        assert gh.resolve("OWNER", "myorg/repo") == "gh-tok"
        assert fj.resolve("OWNER", "myorg/repo") == "fj-tok"

