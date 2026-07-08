from __future__ import annotations

from pr_auto_reviewer.application.ports.outbound.changeset_fetcher_port import (
    ChangesetFetcherPort,
)
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from ._parse_platform_prefix import split_repository_prefix as parse_platform_prefix

class CompositeChangesetFetcher(ChangesetFetcherPort):
    def __init__(
        self,
        github_fetcher: ChangesetFetcherPort,
        forgejo_fetcher: ChangesetFetcherPort,
        default_platform: str = "codeberg",
    ) -> None:
        self._fetchers = {
            "github": github_fetcher,
            "codeberg": forgejo_fetcher,
            "forgejo": forgejo_fetcher,
        }
        self._default_platform = default_platform

    def fetch(self, pr_id: PullRequestId, sha: CommitSha) -> PullRequestDiff:
        platform, clean_repo = parse_platform_prefix(pr_id.repository)
        platform = platform or self._default_platform
        clean_pr_id = PullRequestId(repository=clean_repo, number=pr_id.number)
        fetcher = self._fetchers.get(platform)
        if fetcher is None:
            raise ValueError(f"Unknown platform: {platform}")
        return fetcher.fetch(clean_pr_id, sha)
