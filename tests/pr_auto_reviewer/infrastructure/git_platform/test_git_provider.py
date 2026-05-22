import pytest
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider


class TestGitProvider:

    def test_parse_codeberg_returns_codeberg(self):
        assert GitProvider.parse("codeberg") == GitProvider.CODEBERG

    def test_parse_forgejo_returns_codeberg(self):
        assert GitProvider.parse("forgejo") == GitProvider.CODEBERG

    def test_parse_github_returns_github(self):
        assert GitProvider.parse("github") == GitProvider.GITHUB

    def test_parse_gh_returns_github(self):
        assert GitProvider.parse("gh") == GitProvider.GITHUB

    def test_parse_gitlab_returns_gitlab(self):
        assert GitProvider.parse("gitlab") == GitProvider.GITLAB

    def test_parse_local_returns_local(self):
        assert GitProvider.parse("local") == GitProvider.LOCAL

    def test_parse_localhost_returns_local(self):
        assert GitProvider.parse("localhost") == GitProvider.LOCAL

    def test_parse_unknown_returns_other(self):
        assert GitProvider.parse("bitbucket") == GitProvider.OTHER

    def test_parse_none_returns_other(self):
        assert GitProvider.parse(None) == GitProvider.OTHER

    def test_parse_empty_string_returns_other(self):
        assert GitProvider.parse("") == GitProvider.OTHER

    def test_parse_whitespace_returns_other(self):
        assert GitProvider.parse("   ") == GitProvider.OTHER

    def test_parse_case_insensitive(self):
        assert GitProvider.parse("Codeberg") == GitProvider.CODEBERG

    def test_parse_already_git_provider_returns_same(self):
        assert GitProvider.parse(GitProvider.GITHUB) == GitProvider.GITHUB
