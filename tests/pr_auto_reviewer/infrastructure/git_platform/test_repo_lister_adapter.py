from __future__ import annotations

from pr_auto_reviewer.infrastructure.git_platform.repo_lister_adapter import (
    GitRepoListerAdapter,
)

from tests.fakes.http_client import FakeGitPlatformHttpClient
from tests.fixtures.repo_lister_fixtures import user_dict, repo_dicts


class TestGitRepoListerAdapter:

    def test_list_repos_when_user_owns_repos_then_returns_owned_names(self):
        client = FakeGitPlatformHttpClient({"/user": user_dict(), "/user/repos": repo_dicts()})
        adapter = GitRepoListerAdapter(client)
        assert adapter.list_repos() == ["testuser/repo-a", "testuser/repo-b"]

    def test_list_repos_when_filter_set_then_short_circuits_without_api_call(self):
        client = FakeGitPlatformHttpClient({})
        adapter = GitRepoListerAdapter(client, repos_filter="owner/my-repo")
        assert adapter.list_repos() == ["owner/my-repo"]

    def test_list_repos_when_owner_field_is_username_then_filters_by_owner(self):
        repos = [{"full_name": "x/filtered", "owner": {"username": "x"}}]
        client = FakeGitPlatformHttpClient({"/user": {"login": "x"}, "/user/repos": repos})
        adapter = GitRepoListerAdapter(client)
        assert adapter.list_repos() == ["x/filtered"]

    def test_list_repos_when_response_is_paginated_dict_then_unwraps_data_key(self):
        repos = [{"full_name": "u/r1", "owner": {"login": "u"}}]
        client = FakeGitPlatformHttpClient({"/user": user_dict("u"), "/user/repos": {"data": repos}})
        adapter = GitRepoListerAdapter(client)
        assert adapter.list_repos() == ["u/r1"]

    def test_list_repos_when_user_api_throws_then_returns_empty_list(self):
        client = FakeGitPlatformHttpClient({"/user": ConnectionError("down")})
        adapter = GitRepoListerAdapter(client)
        assert adapter.list_repos() == []

    def test_list_repos_when_user_has_no_username_then_returns_empty_list(self):
        client = FakeGitPlatformHttpClient({"/user": {"no": "username"}})
        adapter = GitRepoListerAdapter(client)
        assert adapter.list_repos() == []

    def test_list_repos_when_repos_api_throws_then_returns_empty_list(self):
        client = FakeGitPlatformHttpClient({"/user": user_dict(), "/user/repos": ConnectionError("gone")})
        adapter = GitRepoListerAdapter(client)
        assert adapter.list_repos() == []
