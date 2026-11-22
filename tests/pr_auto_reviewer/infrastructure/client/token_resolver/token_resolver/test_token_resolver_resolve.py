from ._helpers import *


class TestTokenResolverResolve:
    def test_resolve_returns_default_manager_token(self):
        resolver = _resolver()
        assert resolver.resolve("MANAGER", "myorg/repo") == "default-manager"

    def test_resolve_returns_default_reviewer_token(self):
        resolver = _resolver()
        assert resolver.resolve("REVIEWER", "myorg/repo") == "default-reviewer"

    def test_resolve_returns_org_override_owner(self):
        resolver = _resolver(GITHUB_TOKEN_myorg_MANAGER="org-own")
        assert resolver.resolve("MANAGER", "myorg/repo") == "org-own"

    def test_resolve_returns_org_override_reviewer(self):
        resolver = _resolver(GITHUB_TOKEN_myorg_REVIEWER="org-rev")
        assert resolver.resolve("REVIEWER", "myorg/repo") == "org-rev"

    def test_resolve_returns_default_when_other_role_has_org_override(self):
        resolver = _resolver(GITHUB_TOKEN_myorg_REVIEWER="org-rev")
        assert resolver.resolve("MANAGER", "myorg/repo") == "default-manager"

    def test_resolve_falls_back_to_default_when_repo_is_empty(self):
        resolver = _resolver(GITHUB_TOKEN_myorg_MANAGER="org-own")
        assert resolver.resolve("MANAGER", "") == "default-manager"

    def test_resolve_falls_back_to_default_when_repo_has_no_slash(self):
        resolver = _resolver(GITHUB_TOKEN_myrepo_MANAGER="org-own")
        assert resolver.resolve("MANAGER", "myrepo") == "default-manager"

    def test_resolve_returns_empty_for_unknown_role(self):
        resolver = _resolver(GITHUB_TOKEN_myorg_MANAGER="org-own")
        assert resolver.resolve("BOGUS", "myorg/repo") == ""

    def test_resolve_matches_lowercase_role_argument(self):
        resolver = _resolver(GITHUB_TOKEN_myorg_MANAGER="tok")
        assert resolver.resolve("manager", "myorg/repo") == "tok"

    def test_resolve_matches_lowercase_platform_prefix(self):
        resolver = _resolver(platform_prefix="github", GITHUB_TOKEN_myorg_MANAGER="tok")
        assert resolver.resolve("MANAGER", "myorg/repo") == "tok"

    def test_resolve_handles_org_name_with_underscores(self):
        resolver = _resolver(GITHUB_TOKEN_my_org_name_MANAGER="tok")
        assert resolver.resolve("MANAGER", "my_org_name/repo") == "tok"

    def test_resolve_returns_longest_suffix_match_for_overlapping_orgs(self):
        resolver = _resolver(
            GITHUB_TOKEN_foo_MANAGER="foo-tok",
            GITHUB_TOKEN_foo_org_MANAGER="foo-org-tok",
        )
        assert resolver.resolve("MANAGER", "foo_org/repo") == "foo-org-tok"

