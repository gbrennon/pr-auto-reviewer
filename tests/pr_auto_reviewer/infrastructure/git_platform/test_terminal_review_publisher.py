import pytest
from pr_auto_reviewer.infrastructure.git_platform.terminal_review_publisher import (
    TerminalReviewPublisherAdapter,
)
from pr_auto_reviewer.domain import (
    CodeReview, ReviewVerdict, PullRequestId, ItemSeverity, ReviewItem,
)


class TestTerminalReviewPublisherAdapter:

    @pytest.fixture
    def _publisher(self):
        return TerminalReviewPublisherAdapter()

    @pytest.fixture
    def _pr_id(self):
        return PullRequestId(repository="owner/repo", number=42)

    @pytest.fixture
    def _review(self):
        return CodeReview(
            verdict=ReviewVerdict.APPROVED,
            summary="Looks good.",
            items=[
                ReviewItem(
                    number=1, severity=ItemSeverity.INFO,
                    category="style", file_path="x.py",
                    description="Consider adding type hints.",
                ),
            ],
            model_used="test-model",
        )

    def test_publish_prints_review_to_stdout(
        self, _publisher, _pr_id, _review, capsys,
    ):
        _publisher.publish(_pr_id, _review)
        captured = capsys.readouterr()
        assert "owner/repo#42" in captured.out

    def test_publish_includes_verdict(
        self, _publisher, _pr_id, _review, capsys,
    ):
        _publisher.publish(_pr_id, _review)
        captured = capsys.readouterr()
        assert "Approved" in captured.out

    def test_publish_includes_summary(
        self, _publisher, _pr_id, _review, capsys,
    ):
        _publisher.publish(_pr_id, _review)
        captured = capsys.readouterr()
        assert "Looks good." in captured.out

    def test_publish_includes_items(
        self, _publisher, _pr_id, _review, capsys,
    ):
        _publisher.publish(_pr_id, _review)
        captured = capsys.readouterr()
        assert "Consider adding type hints." in captured.out

    def test_publish_includes_model_used(
        self, _publisher, _pr_id, _review, capsys,
    ):
        _publisher.publish(_pr_id, _review)
        captured = capsys.readouterr()
        assert "test-model" in captured.out
