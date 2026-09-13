"""GithubPrLister — lists open PRs and fetches individual PRs."""

from __future__ import annotations

import logging
from typing import cast

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

class GithubPrLister(PrListerPort):
    """Lists open PRs and fetches individual PRs by number."""

    def __init__(self, client: GitPlatformHttpClient) -> None:
        self._client = client

    def list_open(self, repository: str) -> list[OpenPullRequest]:
        _, repository = split_repository_prefix(repository)
        logger.info("Listing open PRs for %s", repository)
        try:
            data = self._client.get(
                f"/repos/{repository}/pulls",
                state="open",
                per_page=100,
                repo=repository,
            )
            result = [
                pr
                for raw_pr in self._payload_rows(data)
                if (pr := self._parse_pull_request(repository, raw_pr)) is not None
                and not pr.is_draft
            ]
            logger.debug("Found %d open PRs in %s", len(result), repository)
            return result
        except (requests.RequestException, OSError, ValueError, TypeError, KeyError) as exc:
            logger.warning("Failed to list PRs for %s: %s", repository, exc)
            return []

    def list_recent(
        self, repository: str, since: str
    ) -> list[OpenPullRequest]:
        """List open and recently closed PRs updated since ``since``."""
        _, repository = split_repository_prefix(repository)
        try:
            data = self._client.get(
                f"/repos/{repository}/pulls",
                state="all",
                since=since,
                sort="updated",
                direction="desc",
                per_page=100,
                repo=repository,
            )
            return [
                pr
                for raw_pr in self._payload_rows(data)
                if (pr := self._parse_pull_request(repository, raw_pr)) is not None
                and not pr.is_draft
            ]
        except (requests.RequestException, OSError, ValueError, TypeError, KeyError):
            logger.warning("Failed to list recent PRs for %s", repository)
            return []

    @staticmethod
    def _payload_rows(payload: object) -> list[dict[str, object]]:
        if isinstance(payload, list):
            return [cast(dict[str, object], row) for row in payload if isinstance(row, dict)]
        if isinstance(payload, dict):
            return GithubPrLister._payload_rows(payload.get("data", []))
        return []

    @staticmethod
    def _parse_pull_request(
        repository: str, pull_request: dict[str, object]
    ) -> OpenPullRequest | None:
        number = pull_request.get("number")
        if not isinstance(number, int):
            return None
        head = pull_request.get("head")
        base = pull_request.get("base")
        if not isinstance(head, dict):
            return None
        base = base if isinstance(base, dict) else {}
        sha = head.get("sha")
        if not isinstance(sha, str) or not sha:
            return None
        title = pull_request.get("title")
        description = pull_request.get("body")
        updated_at = pull_request.get("updated_at")
        target_branch = base.get("ref")
        return OpenPullRequest(
            pr_id=PullRequestId(repository=repository, number=number),
            head_sha=CommitSha(sha),
            title=title if isinstance(title, str) else "",
            description=description if isinstance(description, str) else "",
            is_draft=pull_request.get("draft") is True,
            review_requested=bool(pull_request.get("requested_reviewers")),
            updated_at=updated_at if isinstance(updated_at, str) else "",
            target_branch=target_branch if isinstance(target_branch, str) else "",
        )

    def get_pr(self, repository: str, pr_number: int) -> OpenPullRequest | None:
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
            target_branch = pr.get("base", {}).get("ref", "")
            description = pr.get("body", "")
            review_requested = bool(pr.get("requested_reviewers"))

            if not number or not sha:
                logger.warning("PR %s #%d has no number or sha", repository, pr_number)
                return None

            return OpenPullRequest(
                pr_id=PullRequestId(repository=repository, number=int(number)),
                head_sha=CommitSha(sha),
                title=title,
                description=description,
                review_requested=review_requested,
                updated_at=pr.get("updated_at", ""),
                target_branch=target_branch,
            )

        except (requests.RequestException, OSError, ValueError, TypeError, KeyError) as exc:
            logger.warning("Failed to fetch PR %s #%d: %s", repository, pr_number, exc)
            return None
