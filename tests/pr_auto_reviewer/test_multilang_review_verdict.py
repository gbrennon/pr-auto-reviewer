"""Multi-language review verdict tests: 7 languages, multiple scenarios.

Each scenario has a .diff fixture and a .full fixture.
Tests use stubs throughout — the CodeReview is constructed inline.
No @patch, no MagicMock.
"""

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

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

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

class TestChangesRequestedMultilang:

    def test_python_sql_injection(self) -> None:
        r, _ = _run_review("python-sql-injection",
            CodeReview(
                verdict=ReviewVerdict.CHANGES_REQUESTED,
                items=[
                    ReviewItem(
                        number=1,
                        severity=ItemSeverity.CRITICAL,
                        category=IssueCategory.SECURITY,
                        file_path="app/repository.py",
                        description="SQL injection vulnerability in user query",
                    ),
                ],
            ),
                           "app/repository.py")
        assert r.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(r.items) == 1
        assert r.items[0].file_path == "app/repository.py"
        assert "sql injection" in r.items[0].description.lower()

    def test_java_god_class(self) -> None:
        r, _ = _run_review("java-god-class",
            CodeReview(
                verdict=ReviewVerdict.CHANGES_REQUESTED,
                items=[
                    ReviewItem(
                        number=1,
                        severity=ItemSeverity.CRITICAL,
                        category=IssueCategory.DESIGN,
                        file_path="src/main/java/com/example/OrderService.java",
                        description="God object pattern detected — class has too many responsibilities",
                    ),
                ],
            ),
                           "src/main/java/com/example/OrderService.java")
        assert r.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(r.items) == 1
        assert r.items[0].file_path == \
            "src/main/java/com/example/OrderService.java"
        assert "god object" in r.items[0].description.lower()

    def test_go_no_error_handling(self) -> None:
        r, _ = _run_review("go-no-error-handling",
            CodeReview(
                verdict=ReviewVerdict.CHANGES_REQUESTED,
                items=[
                    ReviewItem(
                        number=1,
                        severity=ItemSeverity.MAJOR,
                        category=IssueCategory.BUG,
                        file_path="pkg/handler/user.go",
                        description="Unhandled error in file operation",
                    ),
                ],
            ),
                           "pkg/handler/user.go")
        assert r.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(r.items) == 1
        assert r.items[0].file_path == "pkg/handler/user.go"

    def test_ruby_hardcoded_secret(self) -> None:
        r, _ = _run_review("ruby-hardcoded-secret",
            CodeReview(
                verdict=ReviewVerdict.CHANGES_REQUESTED,
                items=[
                    ReviewItem(
                        number=1,
                        severity=ItemSeverity.CRITICAL,
                        category=IssueCategory.SECURITY,
                        file_path="lib/payment_gateway.rb",
                        description="Hardcoded API secret key exposed",
                    ),
                ],
            ),
                           "lib/payment_gateway.rb")
        assert r.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(r.items) == 1
        assert r.items[0].file_path == "lib/payment_gateway.rb"
        assert "hardcoded" in r.items[0].description.lower()

    def test_csharp_tight_coupling(self) -> None:
        r, _ = _run_review("csharp-tight-coupling",
            CodeReview(
                verdict=ReviewVerdict.CHANGES_REQUESTED,
                items=[
                    ReviewItem(
                        number=1,
                        severity=ItemSeverity.MAJOR,
                        category=IssueCategory.DESIGN,
                        file_path="Services/ReportGenerator.cs",
                        description="Tight coupling to concrete database implementation",
                    ),
                ],
            ),
                           "Services/ReportGenerator.cs")
        assert r.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(r.items) == 1
        assert r.items[0].file_path == "Services/ReportGenerator.cs"

    def test_rust_typo_reverse(self) -> None:
        r, _ = _run_review("rust-typo-reverse",
            CodeReview(
                verdict=ReviewVerdict.CHANGES_REQUESTED,
                items=[
                    ReviewItem(
                        number=1,
                        severity=ItemSeverity.MINOR,
                        category=IssueCategory.TYPO,
                        file_path="src/infrastructure/persistence/json_dose_record_repository.rs",
                        description="Function name 'revese' should be 'reverse'",
                    ),
                ],
            ),
                           "src/infrastructure/persistence/"
                           "json_dose_record_repository.rs")
        assert r.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(r.items) == 1
        assert "src/infrastructure" in r.items[0].file_path

class TestApprovedMultilang:

    def test_rust_clean_service(self) -> None:
        r, _ = _run_review("rust-clean-service",
            CodeReview(verdict=ReviewVerdict.APPROVED),
                           "src/services/user_service.rs")
        assert r.verdict == ReviewVerdict.APPROVED
        assert len(r.items) == 0

    def test_kotlin_clean_service(self) -> None:
        r, _ = _run_review("kotlin-clean-service",
            CodeReview(verdict=ReviewVerdict.APPROVED),
                           "src/main/kotlin/com/example/UserService.kt")
        assert r.verdict == ReviewVerdict.APPROVED
        assert len(r.items) == 0

class TestMultilangPromptContents:
    """Verify that FakeReviewContextFactory.build() received the correct
    PullRequestDiff data (including file_paths) for each scenario."""

    SCENARIOS: ClassVar[list[tuple[str, str, str]]] = [
        ("python-sql-injection", "app/repository.py", "sqlite3"),
        ("java-god-class", "src/main/java/com/example/OrderService.java", "OrderService"),
        ("go-no-error-handling", "pkg/handler/user.go", "func CreateUser"),
        ("rust-clean-service", "src/services/user_service.rs", "UserRepository"),
        ("ruby-hardcoded-secret", "lib/payment_gateway.rb", "PaymentGateway"),
        ("csharp-tight-coupling", "Services/ReportGenerator.cs", "SqlConnection"),
        ("kotlin-clean-service", "src/main/kotlin/com/example/UserService.kt", "UserRepository"),
    ]

    @pytest.mark.parametrize("diff_name,file_path,keyword", SCENARIOS)
    def test_file_contents_passed_to_context_factory(
        self,
        diff_name: str,
        file_path: str,
        keyword: str,
    ) -> None:
        """FakeReviewContextFactory.build_calls contain the diff with the
        correct file_paths and file content keyword."""
        _, ctx_factory = _run_review(
            diff_name,
            CodeReview(verdict=ReviewVerdict.APPROVED),
            file_path,
            file_content=keyword,
        )

        assert len(ctx_factory.build_calls) == 1
        _pr_id, diff, pr_title, _pr_description = ctx_factory.build_calls[0]

        assert file_path in diff.file_contents
        assert keyword in diff.file_contents[file_path]
        assert pr_title == "Test"
