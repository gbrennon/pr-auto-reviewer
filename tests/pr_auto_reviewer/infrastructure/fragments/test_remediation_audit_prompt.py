from pathlib import Path


class TestRemediationAuditPrompt:
    """The remediation-audit fragment demands proof and defines output."""

    def test_prompt_demands_proof_and_defines_output(self) -> None:
        path = Path(
            "src/pr_auto_reviewer/infrastructure/fragments/content/"
            "universal/remediation-audit.md"
        )
        text = path.read_text()
        lower = text.lower()
        assert "{findings}" in text
        assert "resolved" in lower and "open" in lower
        assert "reproduction" in lower and "acceptance criteria" in lower
        assert "do not assume" in lower or "never resolve" in lower
        assert '"results"' in text
