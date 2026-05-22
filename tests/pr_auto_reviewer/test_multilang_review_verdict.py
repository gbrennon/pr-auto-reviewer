"""Multi-language review verdict tests: 7 languages, multiple scenarios.

Each scenario has a .diff fixture, .full fixture, and an Ollama response fixture.
Tests use stubs throughout — the CodeReview is parsed from the fixture.
No @patch, no MagicMock.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pr_auto_reviewer.application.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)
from pr_auto_reviewer.application.services.review_pull_request_service import (
    ReviewPullRequestService,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)

from tests.pr_auto_reviewer.application.stubs import (
    StubChangesetFetcher,
    StubLlmReview,
    StubPullRequestRepository,
    StubReviewContextFactory,
    StubReviewPublisher,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _load(relative: str) -> str:
    return (FIXTURES / relative).read_text()


# ── helper ────────────────────────────────────────────────────────────


def _run_review(
    diff_name: str,
    ollama_fixture: str,
    file_path: str,
) -> tuple[CodeReview, StubReviewContextFactory]:
    """Execute the full pipeline with stub ports. Returns published review
    and the context factory for inspection of build_calls."""
    diff = PullRequestDiff(
        pr_id=PullRequestId(repository="o/r", number=1),
        head_sha=CommitSha("abc"),
        diff_content=_load(f"diffs/{diff_name}.diff"),
        file_contents={file_path: _load(f"diffs/{diff_name}.full")},
    )

    raw = json.loads(_load(f"ollama_responses/{ollama_fixture}"))
    review = ReviewResponseParser.parse(raw["response"], "test-model")

    fetcher = StubChangesetFetcher(diff)
    llm_stub = StubLlmReview(review)
    publisher = StubReviewPublisher()
    ctx_factory = StubReviewContextFactory()

    svc = ReviewPullRequestService(
        pr_repository=StubPullRequestRepository(),
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


# ── CHANGES_REQUESTED scenarios ──────────────────────────────────────


class TestChangesRequestedMultilang:

    def test_python_sql_injection(self) -> None:
        r, _ = _run_review("python-sql-injection", "python-sql-injection.json",
                           "app/repository.py")
        assert r.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(r.items) == 1
        assert r.items[0].file_path == "app/repository.py"
        assert "sql injection" in r.items[0].description.lower()

    def test_java_god_class(self) -> None:
        r, _ = _run_review("java-god-class", "java-god-class.json",
                           "src/main/java/com/example/OrderService.java")
        assert r.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(r.items) == 1
        assert r.items[0].file_path == \
            "src/main/java/com/example/OrderService.java"
        assert "god object" in r.items[0].description.lower()

    def test_go_no_error_handling(self) -> None:
        r, _ = _run_review("go-no-error-handling", "go-no-error-handling.json",
                           "pkg/handler/user.go")
        assert r.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(r.items) == 1
        assert r.items[0].file_path == "pkg/handler/user.go"

    def test_ruby_hardcoded_secret(self) -> None:
        r, _ = _run_review("ruby-hardcoded-secret",
                           "ruby-hardcoded-secret.json",
                           "lib/payment_gateway.rb")
        assert r.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(r.items) == 1
        assert r.items[0].file_path == "lib/payment_gateway.rb"
        assert "hardcoded" in r.items[0].description.lower()

    def test_csharp_tight_coupling(self) -> None:
        r, _ = _run_review("csharp-tight-coupling",
                           "csharp-tight-coupling.json",
                           "Services/ReportGenerator.cs")
        assert r.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(r.items) == 1
        assert r.items[0].file_path == "Services/ReportGenerator.cs"

    def test_rust_typo_reverse(self) -> None:
        r, _ = _run_review("rust-typo-reverse", "rust-typo-reverse.json",
                           "src/infrastructure/persistence/"
                           "json_dose_record_repository.rs")
        assert r.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(r.items) == 1
        assert "src/infrastructure" in r.items[0].file_path


# ── APPROVED scenarios ───────────────────────────────────────────────


class TestApprovedMultilang:

    def test_rust_clean_service(self) -> None:
        r, _ = _run_review("rust-clean-service", "rust-clean-service.json",
                           "src/services/user_service.rs")
        assert r.verdict == ReviewVerdict.APPROVED
        assert len(r.items) == 0

    def test_kotlin_clean_service(self) -> None:
        r, _ = _run_review("kotlin-clean-service",
                           "kotlin-clean-service.json",
                           "src/main/kotlin/com/example/UserService.kt")
        assert r.verdict == ReviewVerdict.APPROVED
        assert len(r.items) == 0


# ── cross-cutting: StubReviewContextFactory.build_calls ───────────────


class TestMultilangPromptContents:
    """Verify that StubReviewContextFactory.build() received the correct
    PullRequestDiff data (including file_paths) for each scenario."""

    SCENARIOS = [
        ("python-sql-injection", "python-sql-injection",
         "app/repository.py", "sqlite3"),
        ("java-god-class", "java-god-class",
         "src/main/java/com/example/OrderService.java", "OrderService"),
        ("go-no-error-handling", "go-no-error-handling",
         "pkg/handler/user.go", "func CreateUser"),
        ("rust-clean-service", "rust-clean-service",
         "src/services/user_service.rs", "UserRepository"),
        ("ruby-hardcoded-secret", "ruby-hardcoded-secret",
         "lib/payment_gateway.rb", "PaymentGateway"),
        ("csharp-tight-coupling", "csharp-tight-coupling",
         "Services/ReportGenerator.cs", "SqlConnection"),
        ("kotlin-clean-service", "kotlin-clean-service",
         "src/main/kotlin/com/example/UserService.kt", "UserRepository"),
    ]

    @pytest.mark.parametrize("diff_name,full_name,file_path,keyword", SCENARIOS)
    def test_file_contents_passed_to_context_factory(
        self,
        diff_name: str,
        full_name: str,
        file_path: str,
        keyword: str,
    ) -> None:
        """StubReviewContextFactory.build_calls contain the diff with the
        correct file_paths and file content keyword."""
        _, ctx_factory = _run_review(diff_name, f"{diff_name}.json", file_path)

        assert len(ctx_factory.build_calls) == 1
        _pr_id, diff, pr_title, pr_description = ctx_factory.build_calls[0]

        # The diff passed to build() contains the file_contents map
        assert file_path in diff.file_contents
        assert keyword in diff.file_contents[file_path]
        assert pr_title == "Test"
