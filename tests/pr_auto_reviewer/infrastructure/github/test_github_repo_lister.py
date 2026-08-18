"""Behavioral tests for GithubRepoLister."""

import requests

from pr_auto_reviewer.infrastructure.github.repo_lister import GithubRepoLister
from pr_auto_reviewer.presentation.ports import RepoInfo
from tests.fakes import FakeGitPlatformHttpClient


def _lister(paths: dict, repos_filter: str | None = None) -> GithubRepoLister:
    return GithubRepoLister(FakeGitPlatformHttpClient(paths), repos_filter=repos_filter)


PATH = "/user/repos"


class TestGithubRepoLister:
    """Exercises GithubRepoLister.list_repos across response shapes."""

    def test_list_repos_when_repos_filter_then_returns_singleton(self) -> None:
        lister = _lister({}, repos_filter="o/r")

        assert lister.list_repos() == [RepoInfo(full_name="o/r")]

    def test_list_repos_when_list_response_then_maps_repos(self) -> None:
        lister = _lister({PATH: [{"full_name": "a/b"}, {"full_name": "c/d"}]})

        result = lister.list_repos()

        assert [r.full_name for r in result] == ["a/b", "c/d"]

    def test_list_repos_when_dict_data_then_unwraps(self) -> None:
        lister = _lister({PATH: {"data": [{"full_name": "a/b"}]}})

        assert [r.full_name for r in lister.list_repos()] == ["a/b"]

    def test_list_repos_when_entry_missing_full_name_then_skips(self) -> None:
        lister = _lister({PATH: [{"full_name": "a/b"}, {"pushed_at": "x"}]})

        assert [r.full_name for r in lister.list_repos()] == ["a/b"]

    def test_list_repos_when_pushed_at_present_then_preserved(self) -> None:
        lister = _lister({PATH: [{"full_name": "a/b", "pushed_at": "2024-01-01"}]})

        result = lister.list_repos()

        assert result[0].pushed_at == "2024-01-01"

    def test_list_repos_when_api_raises_then_returns_empty(self) -> None:
        lister = _lister({PATH: requests.RequestException("down")})

        assert lister.list_repos() == []

    def test_list_repos_when_entry_not_a_mapping_then_skips(self) -> None:
        lister = _lister({PATH: ["plain", {"full_name": "a/b"}]})

        assert [r.full_name for r in lister.list_repos()] == ["a/b"]