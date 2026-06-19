"""Multi-platform composite adapters.

Routes by prefixing repository names with ``platform:``, avoiding
changes to ``PullRequestId`` or other domain objects.
"""

from __future__ import annotations

from pr_auto_reviewer.application.ports.outbound.review_publisher_port import ReviewPublisherPort
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.presentation.ports import PrListerPort, RepoListerPort


def _parse(repo: str) -> tuple[str, str]:
    """Split ``platform:owner/name`` into (platform, repo)."""
    if ":" in repo:
        platform, _, name = repo.partition(":")
        return platform, name
    return "codeberg", repo


class CompositeRepoLister(RepoListerPort):
    """Aggregates repos from multiple platforms, prefixing with platform name."""

    def __init__(self, listers: dict[str, RepoListerPort]) -> None:
        self._listers = listers

    def list_repos(self) -> list[str]:
        result: list[str] = []
        for platform, lister in self._listers.items():
            for repo in lister.list_repos():
                result.append(f"{platform}:{repo}")
        return result


class CompositePrLister(PrListerPort):
    """Routes PR listing to the correct platform based on repo prefix."""

    def __init__(self, listers: dict[str, PrListerPort]) -> None:
        self._listers = listers

    def list_open(self, repository: str) -> list:
        from pr_auto_reviewer.presentation.ports import OpenPullRequest
        platform, repo = _parse(repository)
        lister = self._listers.get(platform)
        if not lister:
            return []
        return lister.list_open(repo)

    def get_pr(self, repository: str, pr_number: int):
        platform, repo = _parse(repository)
        lister = self._listers.get(platform)
        if not lister:
            return None
        return lister.get_pr(repo, pr_number)


class CompositeReviewPublisher(ReviewPublisherPort):
    """Routes review publishing to the correct platform."""

    def __init__(self, publishers: dict[str, ReviewPublisherPort]) -> None:
        self._publishers = publishers

    def publish(self, pr_id: PullRequestId, review: CodeReview) -> None:
        platform, _ = _parse(pr_id.repository)
        publisher = self._publishers.get(platform)
        if not publisher:
            raise ValueError(f"No publisher for platform {platform} in {pr_id}")
        publisher.publish(pr_id, review)
