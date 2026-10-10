from pr_auto_reviewer.domain import (
    CodeReview,
    CommitSha,
    ItemSeverity,
    PullRequest,
    PullRequestId,
    ReviewItem,
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


class TestPullRequestLifecycle:
    def test_add_review_skips_blank_item_id_lifecycle(self) -> None:
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="reason",
            summary="summary",
            model_used="model",
            items=[_item("")],
        )

        pr = _pr().add_review(review, CommitSha("sha-2"))

        assert pr.lifecycles == ()

    def test_dismiss_review_items_without_ids_returns_same_aggregate(self) -> None:
        pr = _pr()

        result = pr.dismiss_review_items()

        assert result is pr

    def test_dismiss_review_items_does_not_append_terminal_transition(self) -> None:
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="reason",
            summary="summary",
            model_used="model",
            items=[_item("item-1")],
        )
        pr = _pr().add_review(review, CommitSha("sha-1"))
        dismissed = pr.dismiss_review_items("item-1")

        repeated = dismissed.dismiss_review_items("item-1")

        assert repeated.lifecycles[0].status is ReviewItemStatus.DISMISSED
        assert len(repeated.lifecycles[0].transitions) == len(
            dismissed.lifecycles[0].transitions
        )

    def test_with_derived_lifecycles_reconstructs_dismissed_status(self) -> None:
        item = ReviewItem(
            id="item-1",
            severity=ItemSeverity.INFO,
            category="style",
            file_path="src/a.py",
            description="suggestion",
            status=ReviewItemStatus.DISMISSED,
            status_explanation="Dismissed by command",
        )
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            reason="reason",
            summary="summary",
            model_used="model",
            suggestions=[item],
        )
        pr = _pr()
        legacy = PullRequest(
            id=pr.id,
            title=pr.title,
            head_sha=pr.head_sha,
            reviews=(review,),
        )

        projected = legacy.with_derived_lifecycles()

        assert projected.lifecycles[0].status is ReviewItemStatus.DISMISSED
        assert projected.latest_review_items()[0].status is ReviewItemStatus.DISMISSED

    def test_with_derived_lifecycles_returns_legacy_pr_without_reviews(self) -> None:
        pr = _pr()

        projected = pr.with_derived_lifecycles()

        assert projected is pr

    def test_with_derived_lifecycles_preserves_existing_projection(self) -> None:
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            reason="reason",
            summary="summary",
            model_used="model",
            suggestions=[_item("suggestion-1")],
        )
        pr = _pr().add_review(review, CommitSha("sha-1"))

        projected = pr.with_derived_lifecycles()

        assert projected is pr
