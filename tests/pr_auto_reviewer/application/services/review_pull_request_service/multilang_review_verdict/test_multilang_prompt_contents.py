from typing import ClassVar

from ._helpers import *

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
            CodeReview(verdict=ReviewVerdict.APPROVED, reason="test reason", summary="test summary", model_used="test model"),
            file_path,
            file_content=keyword,
        )

        assert len(ctx_factory.build_calls) == 1
        _pr_id, diff, pr_title, _pr_description = ctx_factory.build_calls[0]

        assert file_path in diff.file_contents
        assert keyword in diff.file_contents[file_path]
        assert pr_title == "Test"
