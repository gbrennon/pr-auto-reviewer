"""PullRequest — the central aggregate root that tracks the review lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..value_objects.code_review import CodeReview
from ..value_objects.comment_id import CommentId
from ..value_objects.commit_sha import CommitSha
from ..value_objects.pull_request_id import PullRequestId
from ..value_objects.review_item_status import ReviewItemStatus
from .review_item import ReviewItem


@dataclass(frozen=True)
class PullRequest:
    """The central aggregate root.

    Tracks the review lifecycle for a single PR across polling cycles.
    Its identity (PullRequestId) is stable across commits.
    State changes over time — head_sha advances, reviews accumulate,
    processed comments grow.

    Immutable. "Mutation" methods return a new PullRequest with the
    updated state — the original instance is never changed.
    """

    id: PullRequestId
    title: str
    head_sha: CommitSha
    unresolved_blocking_ids: frozenset[str] = frozenset()
    created_issue_item_ids: frozenset[str] = frozenset()
    dismissed_item_ids: frozenset[str] = frozenset()
    last_reviewed_at: str | None = None
    is_draft: bool = False
    processed_comment_ids: frozenset[CommentId] = frozenset()
    reviews: tuple[CodeReview, ...] = ()
    last_review_request_event_id: int | None = None
    last_command_checked_at: str | None = None

    def needs_review(self, sha: CommitSha) -> bool:
        """True when sha differs from the last reviewed commit."""
        if not self.reviews:
            return True
        return sha != self.head_sha

    def record_review_request_event(self, event_id: int) -> PullRequest:
        """Record the latest Codeberg review-request timeline event."""
        if (
            self.last_review_request_event_id is not None
            and event_id <= self.last_review_request_event_id
        ):
            return self
        return replace(self, last_review_request_event_id=event_id)
    def add_review(
        self, review: CodeReview, sha: CommitSha,
    ) -> PullRequest:
        """Records a completed review and advances the reviewed sha."""
        return replace(
            self,
            reviews=self.reviews + (review,),
            head_sha=sha,
            dismissed_item_ids=frozenset(),
        )
    def mark_comment_processed(self, comment_id: CommentId) -> PullRequest:
        """Records that a command comment was handled.

        Returns a new PullRequest with the comment added to processed set.
        """
        return replace(
            self,
            processed_comment_ids=self.processed_comment_ids | {comment_id},
        )

    def is_comment_processed(self, comment_id: CommentId) -> bool:
        """Idempotency guard for command processing."""
        return comment_id in self.processed_comment_ids

    def record_command_check(self, activity_timestamp: str) -> PullRequest:
        """Record the PR activity timestamp used for command processing."""
        return replace(self, last_command_checked_at=activity_timestamp)


    def record_created_issue_items(self, *item_ids: str) -> PullRequest:
        """Record review item IDs that already have tracker issues."""
        if not item_ids:
            return self
        return replace(
            self,
            created_issue_item_ids=(
                self.created_issue_item_ids | frozenset(item_ids)
            ),
        )

    def dismiss_review_items(self, *item_ids: str) -> PullRequest:
        """Record non-blocking review items dismissed by a PR command."""
        if not item_ids:
            return self
        return replace(
            self,
            dismissed_item_ids=self.dismissed_item_ids | frozenset(item_ids),
        )

    def with_unresolved_blocking(self, *item_ids: str) -> PullRequest:
        """Record that blocking review items remain unresolved.

        Returns a new PullRequest with item_ids added to the unresolved set.
        Idempotent — adding an already-present ID is a no-op.
        """
        if not item_ids:
            return self
        return replace(
            self,
            unresolved_blocking_ids=self.unresolved_blocking_ids | frozenset(item_ids),
        )

    def with_resolved_blocking(self, *item_ids: str) -> PullRequest:
        """Record that previously-blocking review items have been resolved.

        Returns a new PullRequest with item_ids removed from the unresolved set.
        Idempotent — removing a non-present ID is a no-op.
        """
        if not item_ids:
            return self
        return replace(
            self,
            unresolved_blocking_ids=self.unresolved_blocking_ids - frozenset(item_ids),
        )

    def latest_review_items(self) -> tuple[ReviewItem, ...]:
        """Return current items and suggestions with derived dismissal status."""
        if not self.reviews:
            return ()
        latest = self.reviews[-1]
        return tuple(
            replace(item, status=ReviewItemStatus.DISMISSED)
            if item.id in self.dismissed_item_ids
            else item
            for item in (*latest.items, *latest.suggestions)
        )
