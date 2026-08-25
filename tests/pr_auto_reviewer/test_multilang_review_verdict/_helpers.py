"""Shared helpers, fixtures, and imports for the split test modules."""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest

from pr_auto_reviewer.application.services.review_pull_request_service import (
    ReviewPullRequestService,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from tests.fakes import (
    FakeChangesetFetcher,
    FakeLlmReview,
    FakePullRequestRepository,
    FakeReviewContextFactory,
    FakeReviewPublisher,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"


def _load(relative: str) -> str:
    return (FIXTURES / relative).read_text()


def _run_review(
    diff_name: str,
    review: CodeReview,
    file_path: str,
    file_content: str = "",
) -> tuple[CodeReview, FakeReviewContextFactory]:
    """Execute the full pipeline with stub ports. Returns published review
    and the context factory for inspection of build_calls."""

    diff = PullRequestDiff(
        pr_id=PullRequestId(repository="o/r", number=1),
        head_sha=CommitSha("abc"),
        diff_content=_load(f"diffs/{diff_name}.diff"),
        file_contents={file_path: file_content},
    )

    fetcher = FakeChangesetFetcher(diff)
    llm_stub = FakeLlmReview(review)
    publisher = FakeReviewPublisher()
    ctx_factory = FakeReviewContextFactory()

    svc = ReviewPullRequestService(
        pr_repository=FakePullRequestRepository(),
        changeset_fetcher=fetcher,
        review_context_factory=ctx_factory,
        llm_review=llm_stub,
        review_publisher=publisher,
    )
    svc.execute(ReviewPullRequestCommand(
        pr_id=PullRequestId(repository="o/r", number=1),
        head_sha=CommitSha("abc"),
        title="Test",
    ))

    assert len(publisher.publish_calls) == 1
    return publisher.publish_calls[0][1], ctx_factory


__all__ = ['FIXTURES', 'ClassVar', 'CodeReview', 'CommitSha', 'FakeChangesetFetcher', 'FakeLlmReview', 'FakePullRequestRepository', 'FakeReviewContextFactory', 'FakeReviewPublisher', 'IssueCategory', 'ItemSeverity', 'Path', 'PullRequestDiff', 'PullRequestId', 'ReviewItem', 'ReviewPullRequestCommand', 'ReviewPullRequestService', 'ReviewVerdict', '_load', '_run_review', 'annotations', 'pytest']
