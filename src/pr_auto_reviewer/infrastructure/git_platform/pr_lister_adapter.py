"""Git-PR-lister adapter - lists open PRs in a repository."""

from __future__ import annotations

from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.presentation.ports import OpenPullRequest, PrListerPort


class GitPrListerAdapter(PrListerPort):
    """Lists open (non-draft) PRs in a repository."""

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

                if number and sha:
                    result.append(
                        OpenPullRequest(
                            pr_id=PullRequestId(repository=repository, number=int(number)),
                            head_sha=CommitSha(sha),
                            title=title,
                            is_draft=pr.get("draft", False),
                        )
                    )

            return result

        except Exception:
            return []