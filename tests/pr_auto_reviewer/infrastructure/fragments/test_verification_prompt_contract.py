from pathlib import Path

class TestVerificationPromptContract:
    """Verifier prompts require actual defects, not defensive suggestions."""

    def test_verifier_rejects_safe_or_theoretical_concerns(self) -> None:
        prompt = (
            Path(__file__).parents[4]
            / "src"
            / "pr_auto_reviewer"
            / "infrastructure"
            / "fragments"
            / "content"
            / "universal"
            / "verify-findings.md"
        ).read_text()

        assert "only defensive programming" in prompt
        assert "no actual defect" in prompt
        assert "real, user-impacting defect" in prompt
        assert "merely defensive or theoretical" in prompt
