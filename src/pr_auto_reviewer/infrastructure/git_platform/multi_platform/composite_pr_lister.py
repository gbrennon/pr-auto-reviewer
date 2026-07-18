from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.presentation.ports.pr_lister_port import PrListerPort
from pr_auto_reviewer.presentation.ports.open_pull_request import OpenPullRequest
from pr_auto_reviewer.infrastructure.git_platform.multi_platform._parse_platform_prefix import split_repository_prefix


class CompositePrLister(PrListerPort):
    def __init__(self, listers: dict[str, PrListerPort]) -> None:
        self._listers = listers

    def list_open(self, repository: str) -> list[OpenPullRequest]:
        platform, repo = split_repository_prefix(repository)
        lister = self._listers.get(platform)
        if not lister:
            return []
        prs = lister.list_open(repo)
        return [
            OpenPullRequest(
                pr_id=PullRequestId(
                    repository=f"{platform}:{pr.pr_id.repository}",
                    number=pr.pr_id.number,
                ),
                head_sha=pr.head_sha,
                title=pr.title,
                description=pr.description,
                is_draft=pr.is_draft,
                updated_at=pr.updated_at,
            )
            for pr in prs
        ]

    def get_pr(self, repository: str, pr_number: int) -> OpenPullRequest | None:
        platform, repo = split_repository_prefix(repository)
        lister = self._listers.get(platform)
        if not lister:
            return None
        pr = lister.get_pr(repo, pr_number)
        if pr:
            return OpenPullRequest(
                pr_id=PullRequestId(
                    repository=f"{platform}:{pr.pr_id.repository}",
                    number=pr.pr_id.number,
                ),
                head_sha=pr.head_sha,
                title=pr.title,
                description=pr.description,
                is_draft=pr.is_draft,
                updated_at=pr.updated_at,
            )
        return pr
