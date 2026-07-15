"""Tests for OrgExtractor."""

from pr_auto_reviewer.infrastructure.client.token_resolver.org_extractor import (
    OrgExtractor,
)


class TestOrgExtractor:
    def test_extracts_org_from_repo_path(self):
        assert OrgExtractor.from_repo("myorg/myrepo") == "myorg"

    def test_returns_empty_when_no_slash(self):
        assert OrgExtractor.from_repo("myrepo") == ""

    def test_returns_empty_for_empty_string(self):
        assert OrgExtractor.from_repo("") == ""
