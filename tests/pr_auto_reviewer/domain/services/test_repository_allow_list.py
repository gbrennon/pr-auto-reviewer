"""Tests for RepositoryAllowList domain service."""

from pr_auto_reviewer.domain.services import RepositoryAllowList


class TestRepositoryAllowList:
    """Tests for RepositoryAllowList.allows(repository_full_name)."""

    def test_empty_allow_list_allows_any_repository(self) -> None:
        allow_list = RepositoryAllowList.allowing_every_repository()
        assert allow_list.allows("owner/anything") is True
        assert allow_list.allows("github:owner/anything") is True

    def test_from_empty_entries_allows_any_repository(self) -> None:
        allow_list = RepositoryAllowList.from_entries([])
        assert allow_list.allows("owner/anything") is True
        assert allow_list.allows("forgejo:owner/anything") is True

    def test_configured_list_allows_exact_member(self) -> None:
        allow_list = RepositoryAllowList.from_entries(["owner/repo"])
        assert allow_list.allows("owner/repo") is True

    def test_configured_list_rejects_non_member(self) -> None:
        allow_list = RepositoryAllowList.from_entries(["owner/repo"])
        assert allow_list.allows("owner/other") is False

    def test_matching_is_case_insensitive(self) -> None:
        allow_list = RepositoryAllowList.from_entries(["owner/repo"])
        assert allow_list.allows("Owner/Repo") is True

    def test_entries_with_surrounding_whitespace_are_normalized(self) -> None:
        allow_list = RepositoryAllowList.from_entries(["  owner/repo  "])
        assert allow_list.allows("owner/repo") is True

    def test_blank_repository_name_rejected_when_list_non_empty(self) -> None:
        allow_list = RepositoryAllowList.from_entries(["owner/repo"])
        assert allow_list.allows("   ") is False
        assert allow_list.allows("") is False

    def test_allows_every_repository_property_reflects_emptiness(self) -> None:
        assert RepositoryAllowList.allowing_every_repository().allows_every_repository
        assert not RepositoryAllowList.from_entries(
            ["owner/repo"]
        ).allows_every_repository

    def test_platform_prefixed_entry_allows_matching_platform_repo(self) -> None:
        allow_list = RepositoryAllowList.from_entries(["github:owner/repo"])
        assert allow_list.allows("github:owner/repo") is True

    def test_platform_prefixed_entry_rejects_different_platform(self) -> None:
        allow_list = RepositoryAllowList.from_entries(["github:owner/repo"])
        assert allow_list.allows("forgejo:owner/repo") is False

    def test_codeberg_prefix_normalizes_to_forgejo(self) -> None:
        allow_list = RepositoryAllowList.from_entries(["codeberg:owner/repo"])
        assert allow_list.allows("forgejo:owner/repo") is True
        assert allow_list.allows("codeberg:owner/repo") is True

    def test_forgejo_entry_allows_codeberg_candidate(self) -> None:
        allow_list = RepositoryAllowList.from_entries(["forgejo:owner/repo"])
        assert allow_list.allows("codeberg:owner/repo") is True

    def test_bare_entry_allows_across_all_platforms(self) -> None:
        allow_list = RepositoryAllowList.from_entries(["owner/repo"])
        assert allow_list.allows("github:owner/repo") is True
        assert allow_list.allows("forgejo:owner/repo") is True
        assert allow_list.allows("gitlab:owner/repo") is True
        assert allow_list.allows("github:other/repo") is False

    def test_platform_prefixed_entry_allows_bare_repo_candidate(self) -> None:
        allow_list = RepositoryAllowList.from_entries(["github:owner/repo"])
        assert allow_list.allows("owner/repo") is True
        assert allow_list.allows("other/repo") is False

    def test_platform_prefix_matching_is_case_insensitive(self) -> None:
        allow_list = RepositoryAllowList.from_entries(["GitHub:Owner/Repo"])
        assert allow_list.allows("github:owner/repo") is True
        assert allow_list.allows("GITHUB:OWNER/REPO") is True
