from ._helpers import *


class TestChangesRequestedMultilang:

    def test_python_sql_injection(self) -> None:
        r, _ = _run_review("python-sql-injection",
            CodeReview(
                verdict=ReviewVerdict.CHANGES_REQUESTED,
                items=[
                    ReviewItem(id="id-1",
                        severity=ItemSeverity.CRITICAL,
                        category=IssueCategory.SECURITY,
                        file_path="app/repository.py",
                        description="SQL injection vulnerability in user query",
                    ),
                ],
                reason="test reason",
                summary="test summary",
                model_used="test model",
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
                    ReviewItem(id="id-1",
                        severity=ItemSeverity.CRITICAL,
                        category=IssueCategory.DESIGN,
                        file_path="src/main/java/com/example/OrderService.java",
                        description="God object pattern detected — class has too many responsibilities",
                    ),
                ],
                reason="test reason",
                summary="test summary",
                model_used="test model",
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
                    ReviewItem(id="id-1",
                        severity=ItemSeverity.MAJOR,
                        category=IssueCategory.BUG,
                        file_path="pkg/handler/user.go",
                        description="Unhandled error in file operation",
                    ),
                ],
                reason="test reason",
                summary="test summary",
                model_used="test model",
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
                    ReviewItem(id="id-1",
                        severity=ItemSeverity.CRITICAL,
                        category=IssueCategory.SECURITY,
                        file_path="lib/payment_gateway.rb",
                        description="Hardcoded API secret key exposed",
                    ),
                ],
                reason="test reason",
                summary="test summary",
                model_used="test model",
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
                    ReviewItem(id="id-1",
                        severity=ItemSeverity.MAJOR,
                        category=IssueCategory.DESIGN,
                        file_path="Services/ReportGenerator.cs",
                        description="Tight coupling to concrete database implementation",
                    ),
                ],
                reason="test reason",
                summary="test summary",
                model_used="test model",
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
                    ReviewItem(id="id-1",
                        severity=ItemSeverity.MINOR,
                        category=IssueCategory.TYPO,
                        file_path="src/infrastructure/persistence/json_dose_record_repository.rs",
                        description="Function name 'revese' should be 'reverse'",
                    ),
                ],
                reason="test reason",
                summary="test summary",
                model_used="test model",
            ),
                           "src/infrastructure/persistence/"
                           "json_dose_record_repository.rs")
        assert r.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(r.items) == 1
        assert "src/infrastructure" in r.items[0].file_path

