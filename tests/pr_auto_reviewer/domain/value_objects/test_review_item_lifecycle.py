from dataclasses import FrozenInstanceError

import pytest

from pr_auto_reviewer.domain import (
    CodeReview,
    CommitSha,
    ItemSeverity,
    PullRequest,
    PullRequestId,
    ReviewAuditResult,
    ReviewItem,
    ReviewItemLifecycle,
    ReviewItemStatus,
    ReviewVerdict,
)


def _item(item_id: str, description: str = "finding") -> ReviewItem:
    return ReviewItem(
        id=item_id,
        severity=ItemSeverity.MAJOR,
        category="bug",
        file_path="src/a.py",
        description=description,
    )


def _pr() -> PullRequest:
    return PullRequest(
        id=PullRequestId(repository="owner/repo", number=1),
        title="Test",
        head_sha=CommitSha("sha-1"),
    )


class TestReviewItemLifecycle:
    def test_first_appearance_is_created(self) -> None:
        lifecycle = ReviewItemLifecycle.first_appearance("item-1", "sha-1")

        assert lifecycle.status is ReviewItemStatus.CREATED
        assert lifecycle.first_seen_sha == "sha-1"
        assert lifecycle.last_audited_sha == "sha-1"
        assert lifecycle.transitions[0].from_status is None

    def test_audit_without_proof_opens_item(self) -> None:
        lifecycle = ReviewItemLifecycle.first_appearance("item-1", "sha-1")

        audited = lifecycle.audit("sha-2", present=True, proof=False, explanation="Still present")

        assert audited.status is ReviewItemStatus.OPEN
        assert audited.status_explanation == "Still present"
        assert audited.transitions[-1].to_status is ReviewItemStatus.OPEN

    def test_audit_with_proof_resolves_item(self) -> None:
        lifecycle = ReviewItemLifecycle.first_appearance("item-1", "sha-1")

        audited = lifecycle.audit("sha-2", proof=True, explanation="Proof confirms fix")

        assert audited.status is ReviewItemStatus.RESOLVED
        assert audited.transitions[-1].from_status is ReviewItemStatus.CREATED

    @pytest.mark.parametrize("terminal", [ReviewItemStatus.RESOLVED, ReviewItemStatus.DISMISSED])
    def test_terminal_lifecycle_never_reopens(self, terminal: ReviewItemStatus) -> None:
        lifecycle = ReviewItemLifecycle.first_appearance("item-1", "sha-1")
        if terminal is ReviewItemStatus.RESOLVED:
            lifecycle = lifecycle.audit("sha-2", proof=True)
        else:
            lifecycle = lifecycle.dismiss("sha-2")

        audited = lifecycle.audit("sha-3", proof=False, explanation="No new proof")

        assert audited.status is terminal
        assert audited.last_audited_sha == "sha-3"

    def test_lifecycle_is_immutable(self) -> None:
        lifecycle = ReviewItemLifecycle.first_appearance("item-1", "sha-1")

        with pytest.raises(FrozenInstanceError):
            setattr(lifecycle, "status", ReviewItemStatus.OPEN)


class TestPullRequestLifecycle:
    def test_add_review_creates_created_lifecycle(self) -> None:
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="reason",
            summary="summary",
            model_used="model",
            items=[_item("item-1")],
        )

        pr = _pr().add_review(review, CommitSha("sha-2"))

        assert pr.lifecycles[0].status is ReviewItemStatus.CREATED
        assert pr.latest_review_items()[0].status is ReviewItemStatus.CREATED

    def test_historical_items_deduplicate_by_id_and_project_status(self) -> None:
        first = _item("item-1", "first evidence")
        duplicate = _item("item-1", "duplicate evidence")
        first_review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="reason",
            summary="summary",
            model_used="model",
            items=[first],
        )
        second_review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="reason 2",
            summary="summary 2",
            model_used="model",
            items=[duplicate],
        )

        pr = _pr().add_review(first_review, CommitSha("sha-1"))
        pr = pr.add_review(second_review, CommitSha("sha-2"))
        audited = pr.lifecycles[0].audit("sha-3", proof=False, explanation="Open")
        pr = pr.apply_audit_result(ReviewAuditResult(lifecycles=(audited,)))

        history = pr.historical_items()

        assert len(history) == 1
        assert history[0].description == "first evidence"
        assert history[0].status is ReviewItemStatus.OPEN
        assert history[0].status_explanation == "Open"

    def test_dismissal_updates_terminal_lifecycle_without_mutating_review(self) -> None:
        item = _item("item-1")
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="reason",
            summary="summary",
            model_used="model",
            items=[item],
        )

        pr = _pr().add_review(review, CommitSha("sha-2"))
        dismissed = pr.dismiss_review_items("item-1")

        assert dismissed.lifecycles[0].status is ReviewItemStatus.DISMISSED
        assert dismissed.historical_items()[0].status is ReviewItemStatus.DISMISSED
        assert dismissed.reviews[0].items[0].status is ReviewItemStatus.OPEN
        assert pr.lifecycles[0].status is ReviewItemStatus.CREATED
