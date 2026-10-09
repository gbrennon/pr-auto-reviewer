from pathlib import Path


class TestRemediationAuditPrompt:
    """The remediation-audit fragment defines proof and stable record identity."""

    def test_prompt_demands_proof_and_defines_output(self) -> None:
        path = Path(
            "src/pr_auto_reviewer/infrastructure/fragments/content/"
            "universal/remediation-audit.md"
        )
        text = path.read_text()
        lower = text.lower()

        assert "{findings}" in text
        assert '"results"' in text
        assert '"finding_id"' in text
        assert '"record_type"' in text
        assert "resolved" in lower and "open" in lower
        assert "reproduction" in lower and "acceptance criteria" in lower
        assert "non-empty" in lower and "reasoning" in lower
        assert "suggestion" in lower
        assert "terminal" in lower
        assert "do not assign an old id" in lower
