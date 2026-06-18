from __future__ import annotations
from typing import Any
from pr_auto_reviewer.application.ports.outbound.review_publisher_port import ReviewPublisherPort
from pr_auto_reviewer.application.ports.outbound.review_reader_port import ReviewReaderPort
from pr_auto_reviewer.application.ports.outbound.comment_publisher_port import CommentPublisherPort
from pr_auto_reviewer.application.ports.outbound.comment_reader_port import CommentReaderPort
from pr_auto_reviewer.application.ports.outbound.issue_tracker_port import IssueTrackerPort
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId

class DispatchingReviewPublisher(ReviewPublisherPort):
    """ReviewPublisherPort that routes to the correct provider based on PR platform."""
    def __init__(self, publishers: dict[str, ReviewPublisherPort]) -> None:
        self._publishers = publishers

    def publish_review(self, pr_id: PullRequestId, review: Any) -> None:
        publisher = self._publishers.get(pr_id.platform)
        if not publisher:
            raise ValueError(f"No review publisher for platform {pr_id.platform}")
        publisher.publish_review(pr_id, review)

class DispatchingReviewReader(ReviewReaderPort):
    """ReviewReaderPort that routes to the correct provider based on PR platform."""
    def __init__(self, readers: dict[str, ReviewReaderPort]) -> None:
        self._readers = readers

    def get_latest_review(self, pr_id: PullRequestId) -> str | None:
        reader = self._readers.get(pr_id.platform)
        if not reader:
            raise ValueError(f"No review reader for platform {pr_id.platform}")
        return reader.get_latest_review(pr_id)

class DispatchingCommentPublisher(CommentPublisherPort):
    """CommentPublisherPort that routes to the correct provider based on PR platform."""
    def __init__(self, publishers: dict[str, CommentPublisherPort]) -> None:
        self._publishers = publishers

    def publish_comment(self, pr_id: PullRequestId, comment: str) -> None:
        publisher = self._publishers.get(pr_id.platform)
        if not publisher:
            raise ValueError(f"No comment publisher for platform {pr_id.platform}")
        publisher.publish_comment(pr_id, comment)

class DispatchingCommentReader(CommentReaderPort):
    """CommentReaderPort that routes to the correct provider based on PR platform."""
    def __init__(self, readers: dict[str, CommentReaderPort]) -> None:
        self._readers = readers

    def get_comments(self, pr_id: PullRequestId) -> list[Any]:
        reader = self._readers.get(pr_id.platform)
        if not reader:
            raise ValueError(f"No comment reader for platform {pr_id.platform}")
        return reader.get_comments(pr_id)

class DispatchingIssueTracker(IssueTrackerPort):
    """IssueTrackerPort that routes to the correct provider based on PR platform."""
    def __init__(self, trackers: dict[str, IssueTrackerPort]) -> None:
        self._trackers = trackers

    def create_issue(self, pr_id: PullRequestId, title: str, body: str) -> str:
        tracker = self._trackers.get(pr_id.platform)
        if not tracker:
            raise ValueError(f"No issue tracker for platform {pr_id.platform}")
        return tracker.create_issue(pr_id, title, body)
