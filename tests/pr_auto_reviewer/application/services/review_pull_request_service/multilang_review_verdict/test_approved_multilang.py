from ._helpers import *


class TestApprovedMultilang:

    def test_rust_clean_service(self) -> None:
        r, _ = _run_review("rust-clean-service",
            CodeReview(verdict=ReviewVerdict.APPROVED, reason="test reason", summary="test summary", model_used="test model"),
                           "src/services/user_service.rs")
        assert r.verdict == ReviewVerdict.APPROVED
        assert len(r.items) == 0

    def test_kotlin_clean_service(self) -> None:
        r, _ = _run_review("kotlin-clean-service",
            CodeReview(verdict=ReviewVerdict.APPROVED, reason="test reason", summary="test summary", model_used="test model"),
                           "src/main/kotlin/com/example/UserService.kt")
        assert r.verdict == ReviewVerdict.APPROVED
        assert len(r.items) == 0

