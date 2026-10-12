"""Git-PR-lister adapter - lists open PRs and fetches individual PRs."""

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


class ForgejoPrLister(PrListerPort):
    """Lists open PRs and fetches individual PRs by number."""

    def __init__(self, client: GitPlatformHttpClient) -> None:
        self._client = client

    def list_open(self, repository: str) -> list[OpenPullRequest]:
        """List all open PRs in the given repository."""
        _, repository = split_repository_prefix(repository)
        try:
            payload: object = self._client.get(
                f"/repos/{repository}/pulls",
                state="open",
                limit=100,
                repo=repository,
            )
            prs = self._pull_request_rows(payload)
            result = [
                parsed
                for pr in prs
                if (parsed := self._parse_open_pull_request(repository, pr)) is not None
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
            payload = self._client.get(
                f"/repos/{repository}/pulls",
                state="all",
                since=since,
                sort="updated",
                direction="desc",
                limit=50,
                repo=repository,
            )
            return [
                parsed
                for pr in self._pull_request_rows(payload)
                if (parsed := self._parse_open_pull_request(
                    repository, pr, include_review_event=False
                )) is not None
            ]
        except (requests.RequestException, OSError, ValueError, TypeError, KeyError):
            logger.warning("Failed to list recent PRs for %s", repository)
            return []

    def get_pr(self, repository: str, pr_number: int) -> OpenPullRequest | None:
        """Fetch a single PR by number, regardless of state."""
        _, repository = split_repository_prefix(repository)
        logger.info("Fetching PR %s #%d", repository, pr_number)
        try:
            payload: object = self._client.get(
                f"/repos/{repository}/pulls/{pr_number}",
                repo=repository,
            )
            pr = cast(dict[str, object], payload)
            number = pr.get("number")
            sha = self._string_value(
                self._nested_value(pr.get("head"), "sha")
            )
            if not isinstance(number, int) or not sha:
                logger.warning("PR %s #%d has no number or sha", repository, pr_number)
                return None
            title = self._string_value(pr.get("title"))
            description = self._string_value(pr.get("body"))
            target_branch = self._string_value(
                self._nested_value(pr.get("base"), "ref")
            )
            review_requested = bool(pr.get("requested_reviewers"))
            review_request_event_id = self._latest_review_request_event_id(
                repository, number
            )
            latest_review_id, latest_review_dismissed = (
                self._latest_platform_review(repository, number)
            )
            result = OpenPullRequest(
                pr_id=PullRequestId(repository=repository, number=number),
                head_sha=CommitSha(sha),
                title=title,
                description=description,
                is_draft=self._bool_value(pr.get("draft")),
                review_requested=review_requested,
                review_request_event_id=review_request_event_id,
                latest_review_id=latest_review_id,
                latest_review_dismissed=latest_review_dismissed,
                updated_at=self._string_value(pr.get("updated_at")),
                target_branch=target_branch,
            )
            logger.info(
                "ForgejoPrLister.get_pr return: title='%s' sha=%s",
                title[:60],
                sha[:7],
            )
            return result
        except (requests.RequestException, OSError, ValueError, TypeError, KeyError) as exc:
            logger.warning("Failed to fetch PR %s #%d: %s", repository, pr_number, exc)
            return None

    @staticmethod
    def _pull_request_rows(payload: object) -> list[dict[str, object]]:
        if isinstance(payload, dict):
            payload = payload.get("data", [])
        if not isinstance(payload, list):
            return []
        return [cast(dict[str, object], row) for row in payload if isinstance(row, dict)]

    def _parse_open_pull_request(
        self,
        repository: str,
        pr: dict[str, object],
        include_review_event: bool = True,
    ) -> OpenPullRequest | None:
        draft = self._bool_value(pr.get("draft"))
        number = pr.get("number")
        sha = self._string_value(self._nested_value(pr.get("head"), "sha"))
        if draft or not isinstance(number, int) or not sha:
            return None
        review_request_event_id = (
            self._latest_review_request_event_id(repository, number)
            if include_review_event
            else None
        )
        latest_review_id, latest_review_dismissed = (
            self._latest_platform_review(repository, number)
            if include_review_event
            else (None, False)
        )
        return OpenPullRequest(
            pr_id=PullRequestId(repository=repository, number=number),
            head_sha=CommitSha(sha),
            title=self._string_value(pr.get("title")),
            description=self._string_value(pr.get("body")),
            is_draft=draft,
            review_requested=bool(pr.get("requested_reviewers")),
            review_request_event_id=review_request_event_id,
            latest_review_id=latest_review_id,
            latest_review_dismissed=latest_review_dismissed,
            updated_at=self._string_value(pr.get("updated_at")),
            target_branch=self._string_value(
                self._nested_value(self._nested_value(pr.get("base"), "ref"), "value")
            )
            or self._string_value(self._nested_value(pr.get("base"), "ref")),
        )

    @staticmethod
    def _nested_value(value: object, key: str) -> object:
        if isinstance(value, dict):
            return value.get(key)
        return None

    @staticmethod
    def _string_value(value: object) -> str:
        return value if isinstance(value, str) else ""

    @staticmethod
    def _bool_value(value: object) -> bool:
        return value if isinstance(value, bool) else False

    def _latest_review_request_event_id(
        self, repository: str, pr_number: int
    ) -> int | None:
        """Return the latest Codeberg review-request timeline event ID."""
        try:
            events: object = self._client.get(
                f"/repos/{repository}/issues/{pr_number}/timeline",
                repo=repository,
                limit=100,
            )
            if isinstance(events, dict):
                events = events.get("data", [])
            if not isinstance(events, list):
                return None
            request_ids = [
                event_id
                for row in events
                if isinstance(row, dict)
                and row.get("type") == "review_request"
                and isinstance(event_id := row.get("id"), int)
            ]
            return max(request_ids, default=None)
        except (requests.RequestException, OSError, ValueError, TypeError, KeyError):
            return None

    def _latest_platform_review(
        self, repository: str, pr_number: int
    ) -> tuple[int | None, bool]:
        """Return the latest submitted review ID and dismissal state."""
        try:
            reviews: object = self._client.get(
                f"/repos/{repository}/pulls/{pr_number}/reviews",
                repo=repository,
                limit=100,
            )
            if isinstance(reviews, dict):
                reviews = reviews.get("data", [])
            if not isinstance(reviews, list):
                return None, False
            submitted = [
                row
                for row in reviews
                if isinstance(row, dict)
                and row.get("state") != "REQUEST_REVIEW"
                and isinstance(row.get("id"), int)
            ]
            if not submitted:
                return None, False
            latest = max(
                submitted,
                key=lambda row: (
                    str(row.get("submitted_at", "")),
                    int(row["id"]),
                ),
            )
            state = str(latest.get("state", "")).upper()
            return int(latest["id"]), latest.get("dismissed") is True or state == "DISMISSED"
        except (requests.RequestException, OSError, ValueError, TypeError, KeyError):
            return None, False
