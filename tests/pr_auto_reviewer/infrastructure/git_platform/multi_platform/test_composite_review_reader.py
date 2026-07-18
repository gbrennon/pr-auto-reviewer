"""Tests for CompositeReviewReader using stub port implementations."""

import pytest

from pr_auto_reviewer.application.ports.outbound.review_reader_port import (
    ReviewReaderPort,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.git_platform.multi_platform.composite_review_reader import (
    CompositeReviewReader,
)


class _StubReviewReader(ReviewReaderPort):
    """Stub reader that records calls and returns canned data."""

    def __init__(self, latest_review: str | None) -> None:
        self.get_latest_review_calls: list[PullRequestId] = []
        self._latest_review = latest_review

    def get_latest_review(self, pr_id: PullRequestId) -> str | None:
        self.get_latest_review_calls.append(pr_id)
        return self._latest_review


class TestCompositeReviewReader:
    def test_get_latest_review_routes_to_correct_platform(self):
        github_reader = _StubReviewReader("github-review-body")
        forgejo_reader = _StubReviewReader("forgejo-review-body")
        composite = CompositeReviewReader({
            "github": github_reader,
            "forgejo": forgejo_reader,
        })

        gh_result = composite.get_latest_review(
            PullRequestId(repository="github:owner/repo", number=1)
        )
        fj_result = composite.get_latest_review(
            PullRequestId(repository="codeberg:org/proj", number=2)
        )

        assert gh_result == "github-review-body"
        assert fj_result == "forgejo-review-body"
        assert len(github_reader.get_latest_review_calls) == 1
        assert github_reader.get_latest_review_calls[0].repository == "owner/repo"
        assert len(forgejo_reader.get_latest_review_calls) == 1
        assert forgejo_reader.get_latest_review_calls[0].repository == "org/proj"

    def test_get_latest_review_defaults_to_forgejo_without_prefix(self):
        forgejo_reader = _StubReviewReader("forgejo-review-body")
        composite = CompositeReviewReader({"forgejo": forgejo_reader})

        result = composite.get_latest_review(
            PullRequestId(repository="owner/repo", number=1)
        )

        assert result == "forgejo-review-body"
        assert len(forgejo_reader.get_latest_review_calls) == 1
        assert forgejo_reader.get_latest_review_calls[0].repository == "owner/repo"

    def test_get_latest_review_returns_none_when_reader_returns_none(self):
        forgejo_reader = _StubReviewReader(None)
        composite = CompositeReviewReader({"forgejo": forgejo_reader})

        result = composite.get_latest_review(
            PullRequestId(repository="forgejo:owner/repo", number=1)
        )

        assert result is None

    def test_get_latest_review_raises_for_unknown_platform(self):
        composite = CompositeReviewReader({})

        with pytest.raises(ValueError, match="No review reader for platform"):
            composite.get_latest_review(
                PullRequestId(repository="unknown:owner/repo", number=1)
            )
