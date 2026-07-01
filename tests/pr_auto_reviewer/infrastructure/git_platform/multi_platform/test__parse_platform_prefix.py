import pytest

from pr_auto_reviewer.infrastructure.git_platform.multi_platform._parse_platform_prefix import (
    split_repository_prefix,
)


class TestSplitRepositoryPrefix:
    def test_returns_codeberg_for_unprefixed_repo(self):
        platform, name = split_repository_prefix("owner/repo")
        assert platform == "codeberg"
        assert name == "owner/repo"

    def test_extracts_platform_from_github_prefix(self):
        platform, name = split_repository_prefix("github:owner/repo")
        assert platform == "github"
        assert name == "owner/repo"

    def test_extracts_platform_from_gitlab_prefix(self):
        platform, name = split_repository_prefix("gitlab:owner/repo")
        assert platform == "gitlab"
        assert name == "owner/repo"

    def test_extracts_platform_from_codeberg_prefix(self):
        platform, name = split_repository_prefix("codeberg:owner/repo")
        assert platform == "codeberg"
        assert name == "owner/repo"
