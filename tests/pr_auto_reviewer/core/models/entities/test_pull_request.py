import pytest
from pr_auto_reviewer.core.models import (
    PullRequest,
    PullRequestId,
    CommitSha,
    CodeReview,
    ReviewVerdict,
    ReviewItem,
    ItemSeverity,
    CommentId,
)


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
        assert pr.reviews == ()
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
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="OK")
        pr = pr.add_review(review, CommitSha(value="sha1"))
        assert pr.needs_review(CommitSha(value="sha1")) is False

    def test_add_review_advances_head_sha(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test PR",
            head_sha=CommitSha(value="sha1"),
        )
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="LGTM")
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
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="LGTM")
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
        r1 = CodeReview(verdict=ReviewVerdict.COMMENTED, summary="First pass")
        r2 = CodeReview(verdict=ReviewVerdict.APPROVED, summary="All good")

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

        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="OK")
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
                ReviewItem(
                    number=1,
                    severity=ItemSeverity.CRITICAL,
                    category="security",
                    file_path="src/main.py",
                    description="SQL injection risk",
                ),
            ],
            model_used="llama3",
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
            CodeReview(verdict=ReviewVerdict.APPROVED, summary="ok"),
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
        with pytest.raises(Exception):
            pr.id = PullRequestId(repository="x", number=2)  # type: ignore[misc]

    def test_immutable_field_reassignment(self) -> None:
        pr = PullRequest(
            id=PullRequestId(repository="r", number=1),
            title="Test",
            head_sha=CommitSha(value="abc"),
        )
        with pytest.raises(Exception):
            pr.head_sha = CommitSha(value="def")  # type: ignore[misc]
