from ._helpers import *


class TestPullRequest:
    """Tests for PullRequest aggregate root entity (immutable)."""

    def test_creation(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=42)
        sha = CommitSha(value="abc123")
        pr = PullRequest(id=pr_id, title="Add feature X", head_sha=sha)
        assert pr.id == pr_id
        assert pr.title == "Add feature X"
        assert pr.head_sha == sha
        assert pr.is_draft is False
        assert pr.unresolved_blocking_ids == frozenset()
        assert pr.processed_comment_ids == frozenset()

    def test_creation_with_draft(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=1)
        pr = PullRequest(
            id=pr_id, title="WIP thing", head_sha=CommitSha(value="abc"), is_draft=True
        )
        assert pr.is_draft is True

    def test_needs_review_when_sha_differs(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test PR",
            head_sha=CommitSha(value="sha1"),
        )
        assert pr.needs_review(CommitSha(value="sha2")) is True

    def test_needs_review_when_sha_same(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test PR",
            head_sha=CommitSha(value="sha1"),
        )
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="OK", reason="test reason", model_used="test model")
        pr = pr.add_review(review, CommitSha(value="sha1"))
        assert pr.needs_review(CommitSha(value="sha1")) is False

    def test_add_review_advances_head_sha(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test PR",
            head_sha=CommitSha(value="sha1"),
        )
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="LGTM", reason="test reason", model_used="test model")
        pr = pr.add_review(review, CommitSha(value="sha2"))

        assert pr.head_sha == CommitSha(value="sha2")
        assert len(pr.reviews) == 1
        assert pr.reviews[0] == review

    def test_add_review_does_not_mutate_original(self) -> None:
        original = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test PR",
            head_sha=CommitSha(value="sha1"),
        )
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="LGTM", reason="test reason", model_used="test model")
        updated = original.add_review(review, CommitSha(value="sha2"))

        assert original.reviews == ()
        assert original.head_sha == CommitSha(value="sha1")
        assert updated.reviews == (review,)
        assert updated.head_sha == CommitSha(value="sha2")

    def test_add_multiple_reviews(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test PR",
            head_sha=CommitSha(value="sha1"),
        )
        r1 = CodeReview(verdict=ReviewVerdict.CHANGES_REQUESTED, summary="First pass", reason="test reason", model_used="test model")
        r2 = CodeReview(verdict=ReviewVerdict.APPROVED, summary="All good", reason="test reason", model_used="test model")

        pr = pr.add_review(r1, CommitSha(value="sha2"))
        pr = pr.add_review(r2, CommitSha(value="sha3"))

        assert len(pr.reviews) == 2
        assert pr.head_sha == CommitSha(value="sha3")

    def test_mark_comment_processed(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test PR",
            head_sha=CommitSha(value="abc"),
        )
        cid = CommentId(value="c_1")
        pr = pr.mark_comment_processed(cid)
        assert pr.is_comment_processed(cid) is True

    def test_mark_comment_does_not_mutate_original(self) -> None:
        original = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test PR",
            head_sha=CommitSha(value="abc"),
        )
        cid = CommentId(value="c_1")
        updated = original.mark_comment_processed(cid)

        assert original.processed_comment_ids == frozenset()
        assert updated.processed_comment_ids == frozenset({cid})

    def test_is_comment_processed_false(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test PR",
            head_sha=CommitSha(value="abc"),
        )
        assert pr.is_comment_processed(CommentId(value="never_seen")) is False

    def test_mark_multiple_comments_processed(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test PR",
            head_sha=CommitSha(value="abc"),
        )
        c1 = CommentId(value="c_1")
        c2 = CommentId(value="c_2")
        pr = pr.mark_comment_processed(c1)
        pr = pr.mark_comment_processed(c2)

        assert pr.is_comment_processed(c1) is True
        assert pr.is_comment_processed(c2) is True
        assert len(pr.processed_comment_ids) == 2

    def test_identity_stability_across_reviews(self) -> None:
        pr_id = PullRequestId(repository="r", number=1)
        pr = PullRequest(id=pr_id, title="Test", head_sha=CommitSha(value="s1"))
        assert pr.id == pr_id

        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="OK", reason="test reason", model_used="test model")
        pr = pr.add_review(review, CommitSha(value="s2"))
        assert pr.id == pr_id
        assert pr.id.repository == "r"
        assert pr.id.number == 1

    def test_lifecycle_full_flow(self) -> None:
        """Simulate a full review lifecycle."""
        pr_id = PullRequestId(repository="owner/repo", number=42)
        pr = PullRequest(
            id=pr_id,
            title="Add feature",
            head_sha=CommitSha(value="initial"),
        )

        assert pr.needs_review(CommitSha(value="commit1")) is True

        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            summary="Fix security issue",
            items=[
                ReviewItem(id="id-1",
                    severity=ItemSeverity.CRITICAL,
                    category="security",
                    file_path="src/main.py",
                    description="SQL injection risk",
                ),
            ],
            model_used="llama3",
            reason="test reason",
        )
        pr = pr.add_review(review, CommitSha(value="commit1"))

        assert pr.needs_review(CommitSha(value="commit1")) is False
        assert pr.needs_review(CommitSha(value="commit2")) is True

        cid = CommentId(value="c_42")
        pr = pr.mark_comment_processed(cid)
        assert pr.is_comment_processed(cid) is True

    def test_needs_review_with_no_reviews(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="New PR",
            head_sha=CommitSha(value="abc123"),
        )
        assert pr.needs_review(CommitSha(value="abc123")) is True
        assert pr.needs_review(CommitSha(value="def456")) is True

    def test_needs_review_after_first_review(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test",
            head_sha=CommitSha(value="s1"),
        )
        pr = pr.add_review(
            CodeReview(verdict=ReviewVerdict.APPROVED, summary="ok", reason="test reason", model_used="test model"),
            CommitSha(value="s1"),
        )
        assert pr.needs_review(CommitSha(value="s1")) is False
        assert pr.needs_review(CommitSha(value="s2")) is True

    def test_immutable_id(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test",
            head_sha=CommitSha(value="abc"),
        )
        with pytest.raises(FrozenInstanceError):
            setattr(pr, "id", PullRequestId(repository="x", number=2))

    def test_immutable_field_reassignment(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test",
            head_sha=CommitSha(value="abc"),
        )
        with pytest.raises(FrozenInstanceError):
            setattr(pr, "head_sha", CommitSha(value="def"))

    def test_unresolved_blocking_ids_defaults_to_empty(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test",
            head_sha=CommitSha(value="abc"),
        )
        assert pr.unresolved_blocking_ids == frozenset()

    def test_record_created_issue_items_adds_ids(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test",
            head_sha=CommitSha(value="abc"),
        )

        updated = pr.record_created_issue_items("suggestion-1", "suggestion-2")

        assert updated.created_issue_item_ids == frozenset(
            {"suggestion-1", "suggestion-2"}
        )

    def test_record_created_issue_items_is_idempotent(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test",
            head_sha=CommitSha(value="abc"),
        )

        updated = pr.record_created_issue_items("suggestion-1")
        repeated = updated.record_created_issue_items("suggestion-1")

        assert repeated.created_issue_item_ids == frozenset({"suggestion-1"})

    def test_with_unresolved_blocking_adds_ids(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test",
            head_sha=CommitSha(value="abc"),
        )
        updated = pr.with_unresolved_blocking("a3f2", "b7d1")
        assert updated.unresolved_blocking_ids == frozenset({"a3f2", "b7d1"})

    def test_with_unresolved_blocking_does_not_mutate_original(self) -> None:
        original = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test",
            head_sha=CommitSha(value="abc"),
        )
        updated = original.with_unresolved_blocking("a3f2")
        assert original.unresolved_blocking_ids == frozenset()
        assert updated.unresolved_blocking_ids == frozenset({"a3f2"})

    def test_with_unresolved_blocking_idempotent(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test",
            head_sha=CommitSha(value="abc"),
        )
        pr = pr.with_unresolved_blocking("a3f2")
        pr = pr.with_unresolved_blocking("a3f2")
        assert pr.unresolved_blocking_ids == frozenset({"a3f2"})

    def test_with_unresolved_blocking_no_args_returns_self(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test",
            head_sha=CommitSha(value="abc"),
        )
        result = pr.with_unresolved_blocking()
        assert result is pr

    def test_with_resolved_blocking_removes_ids(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test",
            head_sha=CommitSha(value="abc"),
            unresolved_blocking_ids=frozenset({"a3f2", "b7d1", "c9e4"}),
        )
        updated = pr.with_resolved_blocking("a3f2", "c9e4")
        assert updated.unresolved_blocking_ids == frozenset({"b7d1"})

    def test_with_resolved_blocking_does_not_mutate_original(self) -> None:
        original = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test",
            head_sha=CommitSha(value="abc"),
            unresolved_blocking_ids=frozenset({"a3f2"}),
        )
        updated = original.with_resolved_blocking("a3f2")
        assert original.unresolved_blocking_ids == frozenset({"a3f2"})
        assert updated.unresolved_blocking_ids == frozenset()

    def test_with_resolved_blocking_idempotent(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test",
            head_sha=CommitSha(value="abc"),
            unresolved_blocking_ids=frozenset({"a3f2"}),
        )
        result = pr.with_resolved_blocking("b7d1")
        assert result.unresolved_blocking_ids == frozenset({"a3f2"})

    def test_with_resolved_blocking_no_args_returns_self(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test",
            head_sha=CommitSha(value="abc"),
            unresolved_blocking_ids=frozenset({"a3f2"}),
        )
        result = pr.with_resolved_blocking()
        assert result is pr

    def test_latest_review_items_empty_when_no_reviews(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test",
            head_sha=CommitSha(value="abc"),
        )
        assert pr.latest_review_items() == ()

    def test_latest_review_items_combines_items_and_suggestions(self) -> None:
        item = ReviewItem(
            id="item-1",
            severity=ItemSeverity.CRITICAL,
            category="bug",
            file_path="src/a.py",
            description="Bug description",
        )
        suggestion = ReviewItem(
            id="sugg-1",
            severity=ItemSeverity.INFO,
            category="design",
            file_path="src/b.py",
            description="Design suggestion",
        )
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            summary="Summary",
            reason="Reason",
            model_used="model",
            items=[item],
            suggestions=[suggestion],
        )
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test",
            head_sha=CommitSha(value="abc"),
        ).add_review(review, CommitSha(value="abc"))
        items = pr.latest_review_items()
        assert len(items) == 2
        assert items[0] == item
        assert items[1] == suggestion

    def test_dismiss_review_items_preserves_history_and_categories(self) -> None:
        """Dismissals derive copies without mutating the stored review."""
        item = ReviewItem(
            id="item-1",
            severity=ItemSeverity.MINOR,
            category="bug",
            file_path="src/a.py",
            description="Finding",
        )
        suggestion = ReviewItem(
            id="suggestion-1",
            severity=ItemSeverity.INFO,
            category="style",
            file_path="src/b.py",
            description="Suggestion",
        )
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            summary="Summary",
            reason="Reason",
            model_used="model",
            items=[item],
            suggestions=[suggestion],
        )
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test",
            head_sha=CommitSha(value="abc"),
        ).add_review(review, CommitSha(value="abc"))

        dismissed = pr.dismiss_review_items("suggestion-1")

        assert pr.dismissed_item_ids == frozenset()
        assert dismissed.dismissed_item_ids == frozenset({"suggestion-1"})
        assert dismissed.reviews[-1] == review
        latest = dismissed.latest_review_items()
        assert latest[0] == item
        assert latest[1].status is ReviewItemStatus.DISMISSED
        assert latest[1].category == suggestion.category
        assert latest[1].description == suggestion.description

    def test_dismiss_review_items_is_idempotent(self) -> None:
        """Repeated dismissal IDs do not change aggregate state."""
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test",
            head_sha=CommitSha(value="abc"),
        )

        once = pr.dismiss_review_items("item-1")
        twice = once.dismiss_review_items("item-1")

        assert twice.dismissed_item_ids == frozenset({"item-1"})

    def test_terminal_lifecycle_does_not_reopen_when_id_is_reused(
        self,
    ) -> None:
        """A persisted terminal status cannot be reopened by a raw snapshot."""
        old = ReviewItem(
            id="item-1",
            severity=ItemSeverity.INFO,
            category="style",
            file_path=None,
            description="Old",
        )
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test",
            head_sha=CommitSha(value="abc"),
        ).add_review(
            CodeReview(
                verdict=ReviewVerdict.APPROVED,
                summary="Summary",
                reason="Reason",
                model_used="model",
                suggestions=[old],
            ),
            CommitSha(value="abc"),
        ).dismiss_review_items("item-1")

        updated = pr.add_review(
            CodeReview(
                verdict=ReviewVerdict.APPROVED,
                summary="Summary 2",
                reason="Reason 2",
                model_used="model",
                suggestions=[old],
            ),
            CommitSha(value="def"),
        )

        assert updated.dismissed_item_ids == frozenset()
        assert updated.latest_review_items()[0].status is ReviewItemStatus.DISMISSED
