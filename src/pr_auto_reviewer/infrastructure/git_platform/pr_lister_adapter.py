"""Git-PR-lister adapter - lists open PRs and fetches individual PRs."""

from __future__ import annotations

from typing import Optional

from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.presentation.ports import OpenPullRequest, PrListerPort


class GitPrListerAdapter(PrListerPort):
    """Lists open PRs and fetches individual PRs by number."""

    def __init__(self, client: GitPlatformHttpClient) -> None:
        self._client = client

    def list_open(self, repository: str) -> list[OpenPullRequest]:
        """List all open PRs in the given repository."""
        try:
            data = self._client.get(
                f"/repos/{repository}/pulls",
                state="open",
                limit=20,
            )

            prs = data if isinstance(data, list) else data.get("data", [])

            result = []
            for pr in prs:
                if pr.get("draft", False):
                    continue

                number = pr.get("number")
                sha = pr.get("head", {}).get("sha")
                title = pr.get("title", "")
                description = pr.get("body", "")

                if number and sha:
                    result.append(
                        OpenPullRequest(
                            pr_id=PullRequestId(repository=repository, number=int(number)),
                            head_sha=CommitSha(sha),
                            title=title,
                            description=description,
                            is_draft=pr.get("draft", False),
                        )
                    )

            return result

        except Exception:
            return []

    def get_pr(self, repository: str, pr_number: int) -> Optional[OpenPullRequest]:
        """Fetch a single PR by number, regardless of state."""
        try:
            pr = self._client.get(
                f"/repos/{repository}/pulls/{pr_number}",
            )

            number = pr.get("number")
            sha = pr.get("head", {}).get("sha")
            title = pr.get("title", "")
            description = pr.get("body", "")

            if not number or not sha:
                return None

            return OpenPullRequest(
                pr_id=PullRequestId(repository=repository, number=int(number)),
                head_sha=CommitSha(sha),
                title=title,
                description=description,
                is_draft=pr.get("draft", False),
            )

        except Exception:
            return None
