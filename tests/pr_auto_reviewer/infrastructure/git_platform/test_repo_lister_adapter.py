from __future__ import annotations

from pr_auto_reviewer.infrastructure.forgejo.repo_lister import (
    ForgejoRepoLister,
)
from tests.fakes import FakeGitPlatformHttpClient
from tests.fixtures.repo_lister_fixtures import repo_dicts


class PaginatedRepoClient(FakeGitPlatformHttpClient):
    """Returns repository pages based on the requested page number."""

    def __init__(self, pages: dict[int, list[dict[str, str]]]) -> None:
        super().__init__()
        self._pages = pages

    def get(self, path, headers=None, *, repo=None, **params):
        return self._pages.get(params.get("page", 1), [])


class TestForgejoRepoLister:

    def test_list_repos_returns_all_from_api(self):
        client = FakeGitPlatformHttpClient({"/user/repos": repo_dicts()})
        adapter = ForgejoRepoLister(client)
        result = adapter.list_repos()
        assert [r.full_name for r in result] == ["testuser/repo-a", "testuser/repo-b", "other/repo-c"]
        assert result[0].pushed_at == "2024-01-01T00:00:00Z"

    def test_list_repos_fetches_all_api_pages(self):
        first_page = [
            {"full_name": f"owner/repo-{index}"}
            for index in range(50)
        ]
        client = PaginatedRepoClient(
            {
                1: first_page,
                2: [{"full_name": "owner/repo-50"}],
            }
        )
        adapter = ForgejoRepoLister(client)

        result = adapter.list_repos()

        assert len(result) == 51
        assert result[-1].full_name == "owner/repo-50"

    def test_list_repos_when_filter_set_then_short_circuits_without_api_call(self):
        client = FakeGitPlatformHttpClient({})
        adapter = ForgejoRepoLister(client, repos_filter="owner/my-repo")
        result = adapter.list_repos()
        assert [r.full_name for r in result] == ["owner/my-repo"]
        assert result[0].pushed_at is None

    def test_list_repos_when_response_is_paginated_dict_then_unwraps_data_key(self):
        repos = [{"full_name": "u/r1"}]
        client = FakeGitPlatformHttpClient({"/user/repos": {"data": repos}})
        adapter = ForgejoRepoLister(client)
        result = adapter.list_repos()
        assert [r.full_name for r in result] == ["u/r1"]

    def test_list_repos_when_repos_api_throws_then_returns_empty_list(self):
        client = FakeGitPlatformHttpClient({"/user/repos": ConnectionError("gone")})
        adapter = ForgejoRepoLister(client)
        assert adapter.list_repos() == []
