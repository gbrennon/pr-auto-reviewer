"""Tests for RoleSuffixParser."""

from pr_auto_reviewer.infrastructure.client.token_resolver.role_suffix_parser import (
    RoleSuffixParser,
)


class TestRoleSuffixParser:
    def test_parses_owner_role(self):
        org, role = RoleSuffixParser.parse("myorg_OWNER")
        assert org == "myorg"
        assert role == "OWNER"

    def test_parses_reviewer_role(self):
        org, role = RoleSuffixParser.parse("myorg_REVIEWER")
        assert org == "myorg"
        assert role == "REVIEWER"

    def test_parses_reviewer_username_longest_match_first(self):
        org, role = RoleSuffixParser.parse("myorg_REVIEWER_USERNAME")
        assert org == "myorg"
        assert role == "REVIEWER_USERNAME"

    def test_org_name_with_underscores(self):
        org, role = RoleSuffixParser.parse("my_org_name_OWNER")
        assert org == "my_org_name"
        assert role == "OWNER"

    def test_unknown_role_returns_empty(self):
        org, role = RoleSuffixParser.parse("myorg_BOGUS")
        assert org == ""
        assert role == ""

    def test_empty_string_returns_empty(self):
        org, role = RoleSuffixParser.parse("")
        assert org == ""
        assert role == ""
