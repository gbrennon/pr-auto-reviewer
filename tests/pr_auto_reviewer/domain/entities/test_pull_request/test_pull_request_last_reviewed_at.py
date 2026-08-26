from ._helpers import *


class TestPullRequestLastReviewedAt:
    """Tests for the last_reviewed_at field on the PullRequest aggregate."""



    def test_new_pr_has_none_last_reviewed_at(self) -> None:
        """A newly created PullRequest has last_reviewed_at=None by default."""
        pr = PullRequest(
            id=PullRequestId(repository="owner/repo", number=42),
            title="T",
            head_sha=CommitSha(value="aaa"),
        )
        assert pr.last_reviewed_at is None

    def test_needs_review_is_unaffected_by_last_reviewed_at(self) -> None:
        """needs_review only considers head_sha, not last_reviewed_at."""
        pr = PullRequest(
            id=PullRequestId(repository="owner/repo", number=42),
            title="T",
            head_sha=CommitSha(value="aaa"),
            last_reviewed_at="2025-01-01T00:00:00Z",
        )
        review = CodeReview(verdict=ReviewVerdict.APPROVED, summary="ok", reason="test reason", model_used="test model")
        pr = pr.add_review(review, CommitSha(value="aaa"))
        assert not pr.needs_review(CommitSha(value="aaa"))
        assert pr.needs_review(CommitSha(value="bbb"))
