from __future__ import annotations

from pr_auto_reviewer.infrastructure.forgejo.repo_lister import (
    ForgejoRepoLister,
)

from tests.fakes.http_client import FakeGitPlatformHttpClient
from tests.fixtures.repo_lister_fixtures import repo_dicts

class TestForgejoRepoLister:

    def test_list_repos_returns_all_from_api(self):
        client = FakeGitPlatformHttpClient({"/user/repos": repo_dicts()})
        adapter = ForgejoRepoLister(client)
        assert adapter.list_repos() == ["testuser/repo-a", "testuser/repo-b", "other/repo-c"]

    def test_list_repos_when_filter_set_then_short_circuits_without_api_call(self):
        client = FakeGitPlatformHttpClient({})
        adapter = ForgejoRepoLister(client, repos_filter="owner/my-repo")
        assert adapter.list_repos() == ["owner/my-repo"]

    def test_list_repos_when_response_is_paginated_dict_then_unwraps_data_key(self):
        repos = [{"full_name": "u/r1"}]
        client = FakeGitPlatformHttpClient({"/user/repos": {"data": repos}})
        adapter = ForgejoRepoLister(client)
        assert adapter.list_repos() == ["u/r1"]

    def test_list_repos_when_repos_api_throws_then_returns_empty_list(self):
        client = FakeGitPlatformHttpClient({"/user/repos": ConnectionError("gone")})
        adapter = ForgejoRepoLister(client)
        assert adapter.list_repos() == []
