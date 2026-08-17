"""ReviewReaderPort — retrieve the latest published review body for a PR."""

from __future__ import annotations

from typing import Protocol

from ....domain.value_objects.pull_request_id import PullRequestId


class ReviewReaderPort(Protocol):
    def get_latest_review(self, pr_id: PullRequestId) -> str | None:
        ...
