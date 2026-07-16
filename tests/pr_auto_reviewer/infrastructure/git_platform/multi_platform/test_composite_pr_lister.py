
import pytest

from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.presentation.ports.open_pull_request import OpenPullRequest
from pr_auto_reviewer.presentation.ports.pr_lister_port import PrListerPort
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_pr_lister import (
    CompositePrLister,
)

def _make_open_pr(repository: str, number: int, sha: str) -> OpenPullRequest:
    return OpenPullRequest(
        pr_id=PullRequestId(repository=repository, number=number),
        head_sha=CommitSha(sha),
        title=f"PR #{number}",
    )

class StubPrLister(PrListerPort):
    def __init__(self, open_prs: list[OpenPullRequest]) -> None:
        self._open_prs = open_prs

    def list_open(self, repository: str) -> list[OpenPullRequest]:
        return [pr for pr in self._open_prs if pr.pr_id.repository == repository]

    def get_pr(self, repository: str, pr_number: int) -> OpenPullRequest | None:
        for pr in self._open_prs:
            if pr.pr_id.repository == repository and pr.pr_id.number == pr_number:
                return pr
        return None

class TestCompositePrLister:
    def test_list_open_routes_to_correct_platform(self):
        github_pr = _make_open_pr("owner/repo", 1, "abc123")
        codeberg_pr = _make_open_pr("org/proj", 2, "def456")
        composite = CompositePrLister({
            "github": StubPrLister([github_pr]),
            "forgejo": StubPrLister([codeberg_pr]),
        })

        github_result = composite.list_open("github:owner/repo")
        codeberg_result = composite.list_open("codeberg:org/proj")

        assert len(github_result) == 1
        assert github_result[0].pr_id.number == 1
        assert len(codeberg_result) == 1
        assert codeberg_result[0].pr_id.number == 2

    def test_list_open_returns_empty_for_unknown_platform(self):
        composite = CompositePrLister({})

        result = composite.list_open("unknown:owner/repo")

        assert result == []

    def test_list_open_defaults_to_forgejo_without_prefix(self):
        pr = _make_open_pr("owner/repo", 1, "abc123")
        composite = CompositePrLister({
            "forgejo": StubPrLister([pr]),
        })

        result = composite.list_open("owner/repo")

        assert len(result) == 1
        assert result[0].pr_id.repository == "owner/repo"

    def test_get_pr_routes_to_correct_platform(self):
        github_pr = _make_open_pr("owner/repo", 42, "abc123")
        composite = CompositePrLister({
            "github": StubPrLister([github_pr]),
        })

        result = composite.get_pr("github:owner/repo", 42)

        assert result is not None
        assert result.pr_id.number == 42

    def test_get_pr_returns_none_for_unknown_platform(self):
        composite = CompositePrLister({})

        result = composite.get_pr("unknown:owner/repo", 1)

        assert result is None

    def test_get_pr_returns_none_when_not_found(self):
        pr = _make_open_pr("owner/repo", 1, "abc123")
        composite = CompositePrLister({
            "forgejo": StubPrLister([pr]),
        })

        result = composite.get_pr("codeberg:owner/repo", 999)

        assert result is None
