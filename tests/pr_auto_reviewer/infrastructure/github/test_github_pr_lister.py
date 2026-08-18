"""Behavioral tests for GithubPrLister."""

from dataclasses import FrozenInstanceError

import pytest

from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.infrastructure.github.pr_lister import GithubPrLister
from pr_auto_reviewer.presentation.ports import OpenPullRequest
from tests.fakes import FakeGitPlatformHttpClient
from tests.fixtures.pr_lister_fixtures import pr_dict, pr_dicts


def _adapter(api_data: dict) -> GithubPrLister:
    return GithubPrLister(FakeGitPlatformHttpClient(api_data))


class TestGithubPrLister:
    """Exercises GithubPrLister across response shapes."""

    def test_list_open_when_repo_has_prs_then_returns_open_pull_requests(self) -> None:
        adapter = _adapter({"/repos/o/r/pulls": pr_dicts(3)})

        result = adapter.list_open("o/r")

        assert len(result) == 3
        assert all(isinstance(pr, OpenPullRequest) for pr in result)
        assert [pr.pr_id.number for pr in result] == [1, 2, 3]
        assert all(pr.pr_id.repository == "o/r" for pr in result)

    def test_list_open_when_repo_has_drafts_then_filters_them_out(self) -> None:
        prs = [pr_dict(1, draft=False), pr_dict(2, draft=True), pr_dict(3, draft=False)]
        adapter = _adapter({"/repos/o/r/pulls": prs})

        result = adapter.list_open("o/r")

        assert [pr.pr_id.number for pr in result] == [1, 3]

    def test_list_open_when_response_is_paginated_dict_then_unwraps_data_key(self) -> None:
        adapter = _adapter({"/repos/o/r/pulls": {"data": pr_dicts(2)}})

        assert len(adapter.list_open("o/r")) == 2

    def test_list_open_when_api_throws_then_returns_empty_list(self) -> None:
        adapter = _adapter({"/repos/o/r/pulls": ConnectionError("down")})

        assert adapter.list_open("o/r") == []

    def test_list_open_when_entries_missing_fields_then_drops_bad_entries(self) -> None:
        prs = [
            {"number": 1, "title": "OK", "head": {"sha": "a" * 40}},
            {"title": "No number or sha"},
            {"number": 3, "title": "Also OK", "head": {"sha": "b" * 40}},
        ]
        adapter = _adapter({"/repos/o/r/pulls": prs})

        result = adapter.list_open("o/r")

        assert [pr.pr_id.number for pr in result] == [1, 3]

    def test_list_open_when_metadata_present_then_maps_metadata(self) -> None:
        adapter = _adapter(
            {
                "/repos/o/r/pulls": [
                    {
                        "number": 5,
                        "title": "T",
                        "head": {"sha": "c" * 40},
                        "base": {"ref": "main"},
                        "body": "desc",
                        "requested_reviewers": [{"login": "a"}],
                    }
                ]
            }
        )

        result = adapter.list_open("o/r")[0]

        assert result.target_branch == "main"
        assert result.description == "desc"
        assert result.review_requested is True

    def test_get_pr_when_pr_exists_then_returns_open_pull_request(self) -> None:
        adapter = _adapter({"/repos/o/r/pulls/42": pr_dict(42, "The Answer")})

        result = adapter.get_pr("o/r", 42)

        assert result is not None
        assert result.pr_id.number == 42
        assert result.title == "The Answer"
        assert result.head_sha == CommitSha("a" * 40)

    def test_get_pr_when_api_throws_then_returns_none(self) -> None:
        adapter = _adapter({"/repos/o/r/pulls/1": ConnectionError("down")})

        assert adapter.get_pr("o/r", 1) is None

    def test_get_pr_when_missing_number_then_returns_none(self) -> None:
        adapter = _adapter({"/repos/o/r/pulls/1": {"head": {"sha": "a" * 40}}})

        assert adapter.get_pr("o/r", 1) is None

    def test_get_pr_when_missing_sha_then_returns_none(self) -> None:
        adapter = _adapter({"/repos/o/r/pulls/1": {"number": 1, "title": "X"}})

        assert adapter.get_pr("o/r", 1) is None

    def test_get_pr_when_nonexistent_path_then_returns_none(self) -> None:
        adapter = _adapter({})

        assert adapter.get_pr("o/r", 999) is None

    def test_result_when_frozen_dataclass_then_is_immutable(self) -> None:
        adapter = _adapter({"/repos/o/r/pulls": pr_dicts(1)})
        pr = adapter.list_open("o/r")[0]

        with pytest.raises(FrozenInstanceError):
            setattr(pr, "title", "mutated")

    def test_list_open_with_platform_prefix_then_strips_prefix(self) -> None:
        adapter = _adapter({"/repos/o/r/pulls": pr_dicts(1)})

        result = adapter.list_open("github:o/r")

        assert [pr.pr_id.repository for pr in result] == ["o/r"]