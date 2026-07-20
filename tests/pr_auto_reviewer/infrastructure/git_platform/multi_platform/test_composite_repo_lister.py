
import pytest

from pr_auto_reviewer.presentation.ports.repo_info import RepoInfo
from pr_auto_reviewer.presentation.ports.repo_lister_port import RepoListerPort
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_repo_lister import (
    CompositeRepoLister,
)

class StubRepoLister(RepoListerPort):
    def __init__(self, repos: list[RepoInfo]) -> None:
        self._repos = repos

    def list_repos(self) -> list[RepoInfo]:
        return list(self._repos)

class TestCompositeRepoLister:
    def test_aggregates_repos_from_multiple_platforms(self):
        codeberg_lister = StubRepoLister([RepoInfo("o/r1"), RepoInfo("o/r2")])
        github_lister = StubRepoLister([RepoInfo("o/r3")])
        composite = CompositeRepoLister({
            "forgejo": codeberg_lister,
            "github": github_lister,
        })

        repos = composite.list_repos()
        full_names = [r.full_name for r in repos]

        assert sorted(full_names) == sorted([
            "forgejo:o/r1",
            "forgejo:o/r2",
            "github:o/r3",
        ])

    def test_returns_empty_list_when_no_listers(self):
        composite = CompositeRepoLister({})

        repos = composite.list_repos()

        assert repos == []

    def test_skips_empty_platform_results(self):
        empty_lister = StubRepoLister([])
        nonempty_lister = StubRepoLister([RepoInfo("x/y")])
        composite = CompositeRepoLister({
            "forgejo": empty_lister,
            "github": nonempty_lister,
        })

        repos = composite.list_repos()

        assert [r.full_name for r in repos] == ["github:x/y"]
