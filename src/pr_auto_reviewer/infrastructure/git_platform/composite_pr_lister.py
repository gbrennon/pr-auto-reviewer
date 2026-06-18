from __future__ import annotations
from typing import Any
from pr_auto_reviewer.application.ports.outbound.pull_request_repository import PullRequest
from pr_auto_reviewer.presentation.ports import PrListerPort, RepoListerPort

class CompositePrLister(PrListerPort):
    """PrListerPort that aggregates PRs from multiple providers."""
    def __init__(self, listers: list[PrListerPort]) -> None:
        self._listers = listers

    def list_open(self, repo: str) -> list[PullRequest]:
        all_prs = []
        for lister in self._listers:
            try:
                all_prs.extend(lister.list_open(repo))
            except Exception:
                continue
        return all_prs

    def get_pr(self, repo: str, pr_id: int) -> PullRequest | None:
        for lister in self._listers:
            try:
                pr = lister.get_pr(repo, pr_id)
                if pr:
                    return pr
            except Exception:
                continue
        return None

class CompositeRepoLister(RepoListerPort):
    """RepoListerPort that aggregates repositories from multiple providers."""
    def __init__(self, listers: list[RepoListerPort]) -> None:
        self._listers = listers

    def list_repos(self, filter: str | None = None) -> list[str]:
        all_repos = []
        for lister in self._listers:
            try:
                all_repos.extend(lister.list_repos(filter))
            except Exception:
                continue
        return all_repos
