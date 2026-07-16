"""GithubPrLister — lists open PRs and fetches individual PRs."""

from __future__ import annotations

import logging
from typing import Optional

from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.presentation.ports import OpenPullRequest, PrListerPort

logger = logging.getLogger(__name__)

class GithubPrLister(PrListerPort):
    """Lists open PRs and fetches individual PRs by number."""

    def __init__(self, client: GitPlatformHttpClient) -> None:
        self._client = client

    def list_open(self, repository: str) -> list[OpenPullRequest]:
        logger.info("Listing open PRs for %s", repository)
        try:
            data = self._client.get(
                f"/repos/{repository}/pulls",
                state="open",
                limit=20,
                repo=repository,
            )

            prs = data if isinstance(data, list) else data.get("data", [])

            result = []
            for pr in prs:
                if pr.get("draft", False):
                    continue

                number = pr.get("number")
                sha = pr.get("head", {}).get("sha")
                updated_at = pr.get("updated_at", "") or None
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
                            updated_at=updated_at,
                        )
                    )

            logger.debug("Found %d open PRs in %s", len(result), repository)
            return result

        except Exception as exc:
            logger.warning("Failed to list PRs for %s: %s", repository, exc)
            return []

    def get_pr(self, repository: str, pr_number: int) -> Optional[OpenPullRequest]:
        logger.info("Fetching PR %s #%d", repository, pr_number)
        try:
            pr = self._client.get(
                f"/repos/{repository}/pulls/{pr_number}",
                repo=repository,
            )
            number = pr.get("number")
            sha = pr.get("head", {}).get("sha")
            updated_at = pr.get("updated_at", "") or None
            title = pr.get("title", "")
            description = pr.get("body", "")

            if not number or not sha:
                logger.warning("PR %s #%d has no number or sha", repository, pr_number)
                return None

            return OpenPullRequest(
                pr_id=PullRequestId(repository=repository, number=int(number)),
                head_sha=CommitSha(sha),
                title=title,
                description=description,
                is_draft=pr.get("draft", False),
                updated_at=updated_at,
            )

        except Exception as exc:
            logger.warning("Failed to fetch PR %s #%d: %s", repository, pr_number, exc)
            return None