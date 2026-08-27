from ._helpers import *


class TestTokenResolverResolveSource:
    def test_resolve_source_returns_default_key_when_no_override(self):
        resolver = _resolver()
        _, source = resolver.resolve_source("OWNER", "myorg/repo")
        assert source == "GITHUB_OWNER_TOKEN"

    def test_resolve_source_returns_org_env_var_key(self):
        resolver = _resolver(GITHUB_TOKEN_myorg_OWNER="org-tok")
        _, source = resolver.resolve_source("OWNER", "myorg/repo")
        assert source == "GITHUB_TOKEN_myorg_OWNER"

