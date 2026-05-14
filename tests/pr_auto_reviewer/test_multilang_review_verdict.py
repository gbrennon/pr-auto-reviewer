"""Multi-language E2E verdict tests: 7 languages, multiple architectural scenarios.

Each scenario has a .diff fixture, .full fixture, and an Ollama response fixture.
Tests run through the REAL ReviewPullRequestService + OllamaLlmAdapter pipeline.
Only requests.post is mocked.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

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
from pr_auto_reviewer.domain.value_objects.repository_context import (
    RepositoryContext,
)
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.ollama_llm_adapter import OllamaLlmAdapter

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _load(relative: str) -> str:
    return (FIXTURES / relative).read_text()


# ── scenario definitions ──────────────────────────────────────────────

@pytest.fixture
def ctx() -> RepositoryContext:
    return RepositoryContext(architecture_hint="")


def _run_review(
    diff_name: str,
    ollama_fixture: str,
    file_path: str,
    ctx: RepositoryContext,
) -> CodeReview:
    """Execute the full pipeline with given fixtures. Returns published review."""
    diff = PullRequestDiff(
        pr_id=PullRequestId(repository="o/r", number=1),
        head_sha=CommitSha("abc"),
        diff_content=_load(f"diffs/{diff_name}.diff"),
        file_contents={file_path: _load(f"diffs/{diff_name}.full")},
    )
    fetcher = MagicMock()
    fetcher.fetch.return_value = diff
    ctx_port = MagicMock()
    ctx_port.fetch.return_value = ctx
    publisher = MagicMock()

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = json.loads(
        _load(f"ollama_responses/{ollama_fixture}"),
    )

    with patch("requests.post", return_value=mock_response):
        llm = OllamaLlmAdapter("http://localhost:11434", "test-model")
        svc = ReviewPullRequestService(
            pr_repository=MagicMock(),
            changeset_fetcher=fetcher,
            repository_context=ctx_port,
            llm_review=llm,
            review_publisher=publisher,
        )
        svc.execute(ReviewPullRequestCommand(
            pr_id=PullRequestId(repository="o/r", number=1),
            head_sha=CommitSha("abc"),
            title="Test",
        ))

    publisher.publish.assert_called_once()
    return publisher.publish.call_args[0][1]


# ── CHANGES_REQUESTED scenarios ──────────────────────────────────────


class TestChangesRequestedMultilang:

    @staticmethod
    def _assert_cr(review: CodeReview, *, count: int,
                    keyword: str, path: str) -> None:
        assert review.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(review.items) == count
        first = review.items[0]
        assert first.file_path == path
        assert keyword in first.description.lower()

    # Using REAL captured Ollama responses (hyphen-named fixtures)

    def test_python_sql_injection(self, ctx: RepositoryContext) -> None:
        r = _run_review("python-sql-injection", "python-sql-injection.json",
                         "app/repository.py", ctx)
        assert r.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(r.items) == 1
        assert r.items[0].file_path == "app/repository.py"
        assert "sql injection" in r.items[0].description.lower()

    def test_java_god_class(self, ctx: RepositoryContext) -> None:
        r = _run_review("java-god-class", "java-god-class.json",
                         "src/main/java/com/example/OrderService.java", ctx)
        assert r.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(r.items) == 1
        assert r.items[0].file_path == "src/main/java/com/example/OrderService.java"
        assert "god object" in r.items[0].description.lower()

    def test_go_no_error_handling(self, ctx: RepositoryContext) -> None:
        r = _run_review("go-no-error-handling", "go-no-error-handling.json",
                         "pkg/handler/user.go", ctx)
        assert r.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(r.items) == 1  # real model found 1 issue (SQL injection)
        assert r.items[0].file_path == "pkg/handler/user.go"

    def test_ruby_hardcoded_secret(self, ctx: RepositoryContext) -> None:
        r = _run_review("ruby-hardcoded-secret", "ruby-hardcoded-secret.json",
                         "lib/payment_gateway.rb", ctx)
        assert r.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(r.items) == 1
        assert r.items[0].file_path == "lib/payment_gateway.rb"
        assert "hardcoded" in r.items[0].description.lower()

    def test_csharp_tight_coupling(self, ctx: RepositoryContext) -> None:
        r = _run_review("csharp-tight-coupling", "csharp-tight-coupling.json",
                         "Services/ReportGenerator.cs", ctx)
        assert r.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(r.items) == 1  # real model found 1 issue
        assert r.items[0].file_path == "Services/ReportGenerator.cs"

    def test_rust_typo_reverse(self, ctx: RepositoryContext) -> None:
        r = _run_review("rust-typo-reverse", "rust-typo-reverse.json",
                         "src/infrastructure/persistence/json_dose_record_repository.rs", ctx)
        assert r.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(r.items) == 1
        assert "src/infrastructure" in r.items[0].file_path


# ── APPROVED scenarios ───────────────────────────────────────────────


class TestApprovedMultilang:

    def test_rust_clean_service(self, ctx: RepositoryContext) -> None:
        r = _run_review("rust-clean-service", "rust-clean-service.json",
                         "src/services/user_service.rs", ctx)
        assert r.verdict == ReviewVerdict.APPROVED
        assert len(r.items) == 0

    def test_kotlin_clean_service(self, ctx: RepositoryContext) -> None:
        r = _run_review("kotlin-clean-service", "kotlin-clean-service.json",
                         "src/main/kotlin/com/example/UserService.kt", ctx)
        assert r.verdict == ReviewVerdict.APPROVED
        assert len(r.items) == 0


# ── cross-cutting: no file_contents in prompt ────────────────────────


class TestMultilangPromptContents:

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
    @patch("requests.post")
    def test_file_contents_in_prompt(
        self, mock_post: MagicMock,
        diff_name: str, full_name: str, file_path: str, keyword: str,
        ctx: RepositoryContext,
    ) -> None:
        """Full file contents are included to give the LLM context beyond
        the 3-line diff window, preventing rename-vs-deletion confusion."""
        diff = PullRequestDiff(
            pr_id=PullRequestId(repository="o/r", number=1),
            head_sha=CommitSha("abc"),
            diff_content=_load(f"diffs/{diff_name}.diff"),
            file_contents={file_path: _load(f"diffs/{full_name}.full")},
        )
        fetcher = MagicMock()
        fetcher.fetch.return_value = diff
        ctx_port = MagicMock()
        ctx_port.fetch.return_value = ctx

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "response": '{"issues":[],"summary":"ok","suggestions":[],"praise":[]}',
        }
        mock_post.return_value = mock_response

        llm = OllamaLlmAdapter("http://localhost:11434", "test")
        svc = ReviewPullRequestService(
            pr_repository=MagicMock(),
            changeset_fetcher=fetcher,
            repository_context=ctx_port,
            llm_review=llm,
            review_publisher=MagicMock(),
        )
        svc.execute(ReviewPullRequestCommand(
            pr_id=PullRequestId(repository="o/r", number=1),
            head_sha=CommitSha("abc"), title="Test",
        ))

        mock_post.assert_called_once()
        prompt = mock_post.call_args[1]["json"]["prompt"]
        # Full file contents are included for context
        assert "## Full File Contents" in prompt
        assert "AFTER" in prompt
        # Diff content and markers are still present
        assert "diff --git" in prompt
        assert keyword in prompt
