"""PullRequest — the central aggregate root that tracks the review lifecycle."""

from __future__ import annotations

from dataclasses import dataclass, replace

from ..value_objects.code_review import CodeReview
from ..value_objects.comment_id import CommentId
from ..value_objects.commit_sha import CommitSha
from ..value_objects.pull_request_id import PullRequestId
from ..value_objects.review_audit_result import ReviewAuditResult
from ..value_objects.review_item_lifecycle import ReviewItemLifecycle
from ..value_objects.review_item_status import ReviewItemStatus
from .review_item import ReviewItem


@dataclass(frozen=True)
class PullRequest:
    """The central aggregate root for one pull request's review history.

    State changes return a new instance. CodeReview snapshots remain immutable;
    lifecycle statuses are projected onto item views when records are read.
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
    lifecycles: tuple[ReviewItemLifecycle, ...] = ()


    def with_derived_lifecycles(self) -> PullRequest:
        """Return a copy with legacy review snapshots projected into lifecycles."""
        if self.lifecycles or not self.reviews:
            return self
        return replace(self, lifecycles=self._derive_lifecycles())

    @property
    def lifecycle_projection(self) -> tuple[ReviewItemLifecycle, ...]:
        """Return the immutable lifecycle projection for all known IDs."""
        return self.lifecycles

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
        """Record a completed review and create lifecycles for new records."""
        known = {lifecycle.item_id for lifecycle in self.lifecycles}
        lifecycles = list(self.lifecycles)
        for item in (*review.items, *review.suggestions):
            if item.id and item.id not in known:
                lifecycles.append(
                    ReviewItemLifecycle.first_appearance(
                        item.id,
                        str(sha),
                        item.status_explanation,
                    )
                )
                known.add(item.id)
        return replace(
            self,
            reviews=self.reviews + (review,),
            head_sha=sha,
            dismissed_item_ids=frozenset(),
            lifecycles=tuple(lifecycles),
        )

    def apply_audit_result(self, result: ReviewAuditResult) -> PullRequest:
        """Apply audited lifecycle projections without changing review snapshots."""
        by_id = {lifecycle.item_id: lifecycle for lifecycle in self.lifecycles}
        order = [lifecycle.item_id for lifecycle in self.lifecycles]
        for candidate in result.lifecycles:
            existing = by_id.get(candidate.item_id)
            if existing is None:
                by_id[candidate.item_id] = candidate
                order.append(candidate.item_id)
                continue
            if existing.is_terminal:
                by_id[candidate.item_id] = existing.audit(
                    candidate.last_audited_sha,
                    explanation=candidate.status_explanation,
                )
                continue
            by_id[candidate.item_id] = candidate
        lifecycles = tuple(by_id[item_id] for item_id in order)
        dismissed = self.dismissed_item_ids | frozenset(
            lifecycle.item_id
            for lifecycle in lifecycles
            if lifecycle.status is ReviewItemStatus.DISMISSED
        )
        return replace(self, lifecycles=lifecycles, dismissed_item_ids=dismissed)

    def mark_comment_processed(self, comment_id: CommentId) -> PullRequest:
        """Record that a command comment was handled."""
        return replace(
            self,
            processed_comment_ids=self.processed_comment_ids | {comment_id},
        )

    def is_comment_processed(self, comment_id: CommentId) -> bool:
        """Return whether a command comment has already been handled."""
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
        """Dismiss active review items and update their terminal lifecycles."""
        if not item_ids:
            return self
        by_id = {lifecycle.item_id: lifecycle for lifecycle in self.lifecycles}
        for item_id in item_ids:
            lifecycle = by_id.get(item_id)
            if lifecycle is not None and lifecycle.is_active:
                by_id[item_id] = lifecycle.dismiss(str(self.head_sha))
        lifecycles = tuple(
            by_id[lifecycle.item_id] for lifecycle in self.lifecycles
        )
        return replace(
            self,
            dismissed_item_ids=self.dismissed_item_ids | frozenset(item_ids),
            lifecycles=lifecycles,
        )

    def with_unresolved_blocking(self, *item_ids: str) -> PullRequest:
        """Record that blocking review items remain unresolved."""
        if not item_ids:
            return self
        return replace(
            self,
            unresolved_blocking_ids=self.unresolved_blocking_ids | frozenset(item_ids),
        )

    def with_resolved_blocking(self, *item_ids: str) -> PullRequest:
        """Record that previously-blocking review items have been resolved."""
        if not item_ids:
            return self
        return replace(
            self,
            unresolved_blocking_ids=self.unresolved_blocking_ids - frozenset(item_ids),
        )

    def latest_review_items(self) -> tuple[ReviewItem, ...]:
        """Return latest items and suggestions with lifecycle projections."""
        if not self.reviews:
            return ()
        latest = self.reviews[-1]
        return tuple(
            self._project_item(item)
            for item in (*latest.items, *latest.suggestions)
        )

    def historical_items(self) -> tuple[ReviewItem, ...]:
        """Return deduplicated item evidence from every review snapshot."""
        return self._historical(self._review_items())

    def historical_suggestions(self) -> tuple[ReviewItem, ...]:
        """Return deduplicated suggestion evidence from every review snapshot."""
        return self._historical(self._review_suggestions())

    def _review_items(self) -> tuple[ReviewItem, ...]:
        return tuple(item for review in self.reviews for item in review.items)

    def _review_suggestions(self) -> tuple[ReviewItem, ...]:
        return tuple(
            suggestion for review in self.reviews for suggestion in review.suggestions
        )

    def _historical(self, records: tuple[ReviewItem, ...]) -> tuple[ReviewItem, ...]:
        seen: set[str] = set()
        result: list[ReviewItem] = []
        for item in records:
            if item.id and item.id in seen:
                continue
            if item.id:
                seen.add(item.id)
            result.append(self._project_item(item))
        return tuple(result)

    def _project_item(self, item: ReviewItem) -> ReviewItem:
        lifecycle = next(
            (entry for entry in self.lifecycles if entry.item_id == item.id),
            None,
        )
        if item.id in self.dismissed_item_ids and (
            lifecycle is None or lifecycle.is_active
        ):
            return replace(
                item,
                status=ReviewItemStatus.DISMISSED,
                status_explanation="Dismissed by command",
            )
        if lifecycle is not None:
            return replace(
                item,
                status=lifecycle.status,
                status_explanation=lifecycle.status_explanation,
            )
        return item

    def _derive_lifecycles(self) -> tuple[ReviewItemLifecycle, ...]:
        lifecycles: list[ReviewItemLifecycle] = []
        seen: set[str] = set()
        for item in (*self._review_items(), *self._review_suggestions()):
            if not item.id or item.id in seen:
                continue
            seen.add(item.id)
            lifecycle = ReviewItemLifecycle.first_appearance(
                item.id,
                str(self.head_sha),
                item.status_explanation,
            )
            if item.status is ReviewItemStatus.DISMISSED:
                lifecycle = lifecycle.dismiss(str(self.head_sha))
            elif item.status is ReviewItemStatus.RESOLVED:
                lifecycle = lifecycle.audit(
                    str(self.head_sha), proof=True,
                    explanation=item.status_explanation,
                )
            elif item.status is ReviewItemStatus.OPEN:
                lifecycle = lifecycle.audit(
                    str(self.head_sha), proof=False,
                    explanation=item.status_explanation,
                )
            lifecycles.append(lifecycle)
        for item_id in self.dismissed_item_ids - seen:
            lifecycles.append(
                ReviewItemLifecycle.first_appearance(
                    item_id, str(self.head_sha), "Dismissed by command"
                ).dismiss(str(self.head_sha))
            )
        return tuple(lifecycles)
