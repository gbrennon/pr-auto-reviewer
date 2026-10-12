from pathlib import Path

import pytest

from pr_auto_reviewer.application.services.remediation_audit_service import (
    RemediationAuditService,
)
from pr_auto_reviewer.application.services.review_pull_request_service import (
    ReviewPullRequestService,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.commands.audit_remediation_command import (
    AuditRemediationCommand,
)
from pr_auto_reviewer.domain.messages.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_item_status import ReviewItemStatus
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.command_bus.in_memory_command_bus import (
    InMemoryCommandBus,
)
from pr_auto_reviewer.infrastructure.persistence.json_file_pr_repository import (
    JsonFilePullRequestRepository,
)
from tests.fakes.fake_changeset_fetcher import FakeChangesetFetcher
from tests.fakes.fake_llm_review import FakeLlmReview
from tests.fakes.fake_review_context_factory import FakeReviewContextFactory
from tests.fakes.fake_review_publisher import FakeReviewPublisher
from tests.pr_auto_reviewer.application.services.remediation_audit_service.test_execute import (
    FakeAuditTranscriptRunner,
)


@pytest.mark.e2e
class TestReviewItemLifecycleServiceFlow:
    """Exercise review, audit, persistence, and recurrence through real services."""

    def test_audit_resolves_history_and_recurrence_gets_new_id(
        self, tmp_path: Path,
    ) -> None:
        repository = JsonFilePullRequestRepository(tmp_path / "state.json")
        pr_id = PullRequestId(repository="forgejo:owner/repo", number=10)
        first_sha = CommitSha("sha-1")
        second_sha = CommitSha("sha-2")
        finding = ReviewItem(
            id="find-1",
            severity=ItemSeverity.MAJOR,
            category=IssueCategory.BUG,
            file_path="src/example.py",
            description="Validate the parser input.",
            current_code="parse(value)",
        )
        first_review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="The parser accepts invalid input.",
            summary="A blocking finding remains.",
            items=[finding],
            model_used="e2e-model",
        )
        recurrence = ReviewItem(
            id="find-1",
            severity=ItemSeverity.MAJOR,
            category=IssueCategory.BUG,
            file_path="src/example.py",
            description="Validate the parser input.",
            current_code="parse(value)",
        )
        second_review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            reason="The updated review reports no new blocker.",
            summary="Historical remediation was audited.",
            items=[recurrence],
            model_used="e2e-model",
        )
        diff = PullRequestDiff(
            pr_id=pr_id,
            head_sha=second_sha,
            base_sha=first_sha,
            diff_content=(
                "diff --git a/src/example.py b/src/example.py\n"
                "--- a/src/example.py\n"
                "+++ b/src/example.py\n"
                "@@ -1 +1 @@\n"
                "+parse(value)\n"
            ),
            file_contents={"src/example.py": "parse(value)\n"},
            clone_path=tmp_path,
        )
        audit_service = RemediationAuditService(
            FakeAuditTranscriptRunner([
                {
                    "finding_id": "find-1",
                    "status": "resolved",
                    "reasoning": (
                        "src/example.py:1 current source and reproduction "
                        "prove the fix"
                    ),
                }
            ]),
            "{findings}",
        )
        command_bus = InMemoryCommandBus({
            AuditRemediationCommand: audit_service.execute,
        })
        first_publisher = FakeReviewPublisher()
        first_service = ReviewPullRequestService(
            repository,
            FakeChangesetFetcher(diff),
            FakeReviewContextFactory(),
            FakeLlmReview(first_review),
            first_publisher,
            command_bus=command_bus,
        )

        first_service.execute(ReviewPullRequestCommand(
            pr_id=pr_id, head_sha=first_sha, title="Lifecycle flow",
        ))

        second_publisher = FakeReviewPublisher()
        second_service = ReviewPullRequestService(
            repository,
            FakeChangesetFetcher(diff),
            FakeReviewContextFactory(),
            FakeLlmReview(second_review),
            second_publisher,
            command_bus=command_bus,
        )
        second_service.execute(ReviewPullRequestCommand(
            pr_id=pr_id, head_sha=second_sha, title="Lifecycle flow",
        ))

        loaded = repository.find(pr_id)
        assert loaded is not None
        published = second_publisher.publish_calls[0][1]
        assert [item.id for item in published.items] == [
            "find-1", published.items[1].id,
        ]
        assert published.items[1].id != "find-1"
        assert published.items[0].status is ReviewItemStatus.RESOLVED
        assert published.items[1].status is ReviewItemStatus.CREATED
        assert loaded.lifecycles[0].status is ReviewItemStatus.RESOLVED
        assert loaded.lifecycles[1].status is ReviewItemStatus.CREATED
        assert len(loaded.lifecycles[0].transitions) == 2
