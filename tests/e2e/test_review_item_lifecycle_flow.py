from dataclasses import replace
from pathlib import Path

import pytest

from pr_auto_reviewer.domain import (
    CodeReview,
    CommitSha,
    IssueCategory,
    ItemSeverity,
    PullRequest,
    PullRequestId,
    ReviewItem,
    ReviewItemStatus,
    ReviewVerdict,
)
from pr_auto_reviewer.infrastructure.persistence.json_file_pr_repository import (
    JsonFilePullRequestRepository,
)
from pr_auto_reviewer.infrastructure.review_publishers.body_formatter import (
    ReviewBodyRenderer,
)


@pytest.mark.e2e
class TestReviewItemLifecycleFlow:
    """Persist and render historical review records across review rounds."""

    def test_history_preserves_evidence_ids_and_terminal_statuses(
        self, tmp_path: Path,
    ) -> None:
        repository = JsonFilePullRequestRepository(tmp_path / "state.json")
        pr_id = PullRequestId(repository="forgejo:owner/repo", number=9)
        initial_sha = CommitSha("sha-1")
        finding = ReviewItem(
            id="find-1",
            severity=ItemSeverity.MAJOR,
            category=IssueCategory.BUG,
            file_path="src/example.py",
            description="Validate the input before parsing.",
            current_code="parse(value)",
            suggested_fix="validate(value); parse(value)",
        )
        suggestion = ReviewItem(
            id="suggest-1",
            severity=ItemSeverity.INFO,
            category=IssueCategory.GENERAL,
            file_path="src/example.py",
            description="Extract the parser setup into a named helper.",
        )
        first_review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="The parser accepts invalid input.",
            summary="One blocking finding and one suggestion.",
            items=[finding],
            suggestions=[suggestion],
            model_used="e2e-model",
        )
        pull_request = PullRequest(
            id=pr_id,
            title="Lifecycle flow",
            head_sha=initial_sha,
        ).add_review(first_review, initial_sha)
        pull_request = pull_request.dismiss_review_items(suggestion.id)
        repository.save(pull_request)

        second_review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            reason="The new review adds no replacement for historical records.",
            summary="Historical records remain visible.",
            items=[],
            suggestions=[],
            model_used="e2e-model",
        )
        updated = pull_request.add_review(second_review, CommitSha("sha-2"))
        repository.save(updated)

        loaded = repository.find(pr_id)
        assert loaded is not None
        historical_finding = loaded.historical_items()[0]
        historical_suggestion = loaded.historical_suggestions()[0]
        rendered_review = replace(
            second_review,
            items=[historical_finding],
            suggestions=[historical_suggestion],
        )
        body = ReviewBodyRenderer(
            Path(__file__).resolve().parents[2]
            / "src"
            / "pr_auto_reviewer"
            / "infrastructure"
            / "templates"
        ).render(rendered_review)

        assert len(loaded.reviews) == 2
        assert historical_finding.id == finding.id
        assert historical_finding.current_code == finding.current_code
        assert historical_finding.status is ReviewItemStatus.CREATED
        assert historical_suggestion.id == suggestion.id
        assert historical_suggestion.status is ReviewItemStatus.DISMISSED
        assert "`find-1`. [CREATED]" in body
        assert "`suggest-1`. [DISMISSED]" in body
