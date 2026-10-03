from pathlib import Path


class TestPhasePromptsRequestEnrichment:
    """Finding-output phase prompts request remediation context."""

    def test_each_finding_phase_requests_the_four_fields(self) -> None:
        base = Path(
            "src/pr_auto_reviewer/infrastructure/fragments/content/universal"
        )
        for name in (
            "bug-hunt-diff.md",
            "bug-hunt-branch.md",
            "architecture-review.md",
        ):
            text = (base / name).read_text().lower()
            assert "root cause:" in text
            assert "reproduction:" in text
            assert "acceptance criteria:" in text
            assert "detection method:" in text
