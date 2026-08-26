from ._helpers import *


class TestTokenResolverReviewerUsername:
    def test_reviewer_username_returns_default(self):
        resolver = _resolver()
        assert resolver.reviewer_username("myorg/repo") == "default-username"

    def test_reviewer_username_returns_org_override(self):
        resolver = _resolver(GITHUB_TOKEN_myorg_REVIEWER_USERNAME="org-user")
        assert resolver.reviewer_username("myorg/repo") == "org-user"

