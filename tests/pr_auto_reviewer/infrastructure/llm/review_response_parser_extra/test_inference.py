from ._helpers import *


class TestInference:
    """Exercises severity and category inference."""

    def test_infer_severity_when_security_then_critical(self) -> None:
        assert ReviewResponseParser()._infer_severity("sql injection risk") == (
            ItemSeverity.CRITICAL,
            "critical",
        )

    def test_infer_severity_when_crash_then_major(self) -> None:
        assert ReviewResponseParser()._infer_severity("can cause a crash") == (
            ItemSeverity.MAJOR,
            "major",
        )

    def test_infer_severity_when_typo_then_info(self) -> None:
        assert ReviewResponseParser()._infer_severity("typo in comment") == (
            ItemSeverity.INFO,
            "info",
        )

    def test_infer_severity_when_other_then_minor(self) -> None:
        severity, mapped = ReviewResponseParser()._infer_severity("minor improvement")

        assert severity == ItemSeverity.MINOR
        assert mapped == "medium"

    def test_infer_type_when_security_then_security(self) -> None:
        assert ReviewResponseParser()._infer_type("hardcoded secret", "major") == "security"

    def test_infer_type_when_architecture_then_design(self) -> None:
        assert ReviewResponseParser()._infer_type("violates hexagonal boundaries", "major") == "design"

    def test_infer_type_when_test_then_test(self) -> None:
        assert ReviewResponseParser()._infer_type("missing unit test", "minor") == "test"

    def test_infer_type_when_convention_then_maintainability(self) -> None:
        assert ReviewResponseParser()._infer_type("naming convention", "minor") == "maintainability"

    def test_infer_type_when_critical_severity_then_bug(self) -> None:
        assert ReviewResponseParser()._infer_type("unexpected behavior", "critical") == "bug"

    def test_infer_type_when_other_then_quality(self) -> None:
        assert ReviewResponseParser()._infer_type("could be clearer", "minor") == "quality"

