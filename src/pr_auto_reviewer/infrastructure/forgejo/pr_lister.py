"""Git-PR-lister adapter - lists open PRs and fetches individual PRs."""

from __future__ import annotations

import logging

import requests

from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)
from pr_auto_reviewer.infrastructure.git_platform.multi_platform._parse_platform_prefix import (
    split_repository_prefix,
)
from pr_auto_reviewer.presentation.ports import OpenPullRequest, PrListerPort

logger = logging.getLogger(__name__)

class ForgejoPrLister(PrListerPort):
    """Lists open PRs and fetches individual PRs by number."""

    def __init__(self, client: GitPlatformHttpClient) -> None:
        self._client = client

    def list_open(self, repository: str) -> list[OpenPullRequest]:
        """List all open PRs in the given repository."""
        _, repository = split_repository_prefix(repository)
        logger.info("Listing open PRs for %s", repository)
        try:
            data = self._client.get(
                f"/repos/{repository}/pulls",
                state="open",
                limit=100,
                repo=repository,
            )

            prs = data if isinstance(data, list) else data.get("data", [])

            result = []
            for pr in prs:
                if pr.get("draft", False):
                    continue

                number = pr.get("number")
                sha = pr.get("head", {}).get("sha")
                target_branch = pr.get("base", {}).get("ref", "")
                title = pr.get("title", "")
                description = pr.get("body", "")
                review_requested = bool(pr.get("requested_reviewers"))

                if number and sha:
                    result.append(
                        OpenPullRequest(
                            pr_id=PullRequestId(repository=repository, number=int(number)),
                            head_sha=CommitSha(sha),
                            title=title,
                            description=description,
                            is_draft=pr.get("draft", False),
                            review_requested=review_requested,
                            target_branch=target_branch,
                        )
                    )


            logger.debug("Found %d open PRs in %s", len(result), repository)
            pr_summaries = [(p.pr_id.number, p.title[:40], p.head_sha.value[:7]) for p in result]
            logger.info("ForgejoPrLister.list_open return: %s", pr_summaries)
            return result

        except (requests.RequestException, OSError, ValueError, TypeError, KeyError) as exc:
            logger.warning("Failed to list PRs for %s: %s", repository, exc)
            return []

    def get_pr(self, repository: str, pr_number: int) -> OpenPullRequest | None:
        """Fetch a single PR by number, regardless of state."""
        _, repository = split_repository_prefix(repository)
        logger.info("Fetching PR %s #%d", repository, pr_number)
        try:
            pr = self._client.get(
                f"/repos/{repository}/pulls/{pr_number}",
                repo=repository,
            )

            number = pr.get("number")
            sha = pr.get("head", {}).get("sha")
            title = pr.get("title", "")
            description = pr.get("body", "")
            target_branch = pr.get("base", {}).get("ref", "")
            review_requested = bool(pr.get("requested_reviewers"))
            if not number or not sha:
                logger.warning("PR %s #%d has no number or sha", repository, pr_number)
                return None

            logger.debug("Fetched PR %s #%d: '%s'", repository, pr_number, title[:60])
            result = OpenPullRequest(
                pr_id=PullRequestId(repository=repository, number=int(number)),
                head_sha=CommitSha(sha),
                title=title,
                description=description,
                is_draft=pr.get("draft", False),
                review_requested=review_requested,
                target_branch=target_branch,
            )
            logger.info("ForgejoPrLister.get_pr return: title='%s' sha=%s", title[:60], sha[:7])
            return result

        except (requests.RequestException, OSError, ValueError, TypeError, KeyError) as exc:
            logger.warning("Failed to fetch PR %s #%d: %s", repository, pr_number, exc)
            return None
