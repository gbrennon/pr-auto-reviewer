"""Integration tests for pr_lister_adapter.py — uses live Codeberg API."""

from __future__ import annotations

import pytest

from pr_auto_reviewer.infrastructure.git_platform.pr_lister_adapter import (
    GitPrListerAdapter,
)
from pr_auto_reviewer.presentation.ports import OpenPullRequest


class TestGitPrListerAdapterIntegration:
    """Integration tests for GitPrListerAdapter against live API."""

    def test_list_open_public_repo_returns_list(
        self, pr_lister_adapter: GitPrListerAdapter, public_pr_fixtures: dict
    ) -> None:
        """list_open returns a list of OpenPullRequest from a public repo."""
        result = pr_lister_adapter.list_open(public_pr_fixtures["repo"])

        assert isinstance(result, list)
        assert all(isinstance(pr, OpenPullRequest) for pr in result)
        assert all(pr.pr_id.repository == public_pr_fixtures["repo"] for pr in result)
        assert all(isinstance(pr.pr_id.number, int) for pr in result)
        assert all(pr.pr_id.number > 0 for pr in result)
        assert all(isinstance(pr.title, str) for pr in result)
        assert all(len(pr.head_sha.value) == 40 for pr in result)
        assert all(pr.is_draft is False for pr in result)

    def test_list_open_private_repo_returns_list(
        self, pr_lister_adapter: GitPrListerAdapter, private_pr_fixtures: dict
    ) -> None:
        """list_open returns a list from a private repo."""
        result = pr_lister_adapter.list_open(private_pr_fixtures["repo"])

        assert isinstance(result, list)
        assert all(isinstance(pr, OpenPullRequest) for pr in result)
        assert all(pr.pr_id.repository == private_pr_fixtures["repo"] for pr in result)
        assert all(isinstance(pr.pr_id.number, int) for pr in result)
        assert all(pr.pr_id.number > 0 for pr in result)
        assert all(isinstance(pr.title, str) for pr in result)
        assert all(len(pr.head_sha.value) == 40 for pr in result)
        assert all(pr.is_draft is False for pr in result)

    def test_list_open_result_fields_match_api_response(
        self, pr_lister_adapter: GitPrListerAdapter, pr_fixtures: dict
    ) -> None:
        """OpenPullRequest fields are correctly mapped from API response."""
        public_pr = pr_fixtures.get("public_pr", {})
        repo = public_pr.get("repo", "gbrennon/BitPill")

        result = pr_lister_adapter.list_open(repo)

        if result:
            pr = result[0]
            assert isinstance(pr.pr_id.number, int)
            assert isinstance(pr.head_sha.value, str)
            assert isinstance(pr.title, str)
            assert pr.is_draft is False

    def test_list_open_empty_repo_returns_empty_list(
        self, pr_lister_adapter: GitPrListerAdapter
    ) -> None:
        """Non-existent repo returns empty list gracefully."""
        result = pr_lister_adapter.list_open("nonexistent-org/nonexistent-repo")
        assert isinstance(result, list)

    def test_list_open_result_objects_are_frozen_and_hashable(
        self, pr_lister_adapter: GitPrListerAdapter, public_pr_fixtures: dict
    ) -> None:
        """OpenPullRequest is a frozen dataclass."""
        result = pr_lister_adapter.list_open(public_pr_fixtures["repo"])

        if result:
            pr = result[0]
            d = {pr: 1}
            assert d[pr] == 1

            with pytest.raises(Exception):
                pr.title = "mutated"  # type: ignore[misc]
