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

    def test_exploration_tool_contract_forbids_shell_pipelines(self) -> None:
        text = Path(
            "src/pr_auto_reviewer/infrastructure/fragments/content/universal/"
            "reviewer-system-prompt.md"
        ).read_text().lower()
        assert "do not use shell pipes" in text
        assert "read_file" in text
        assert "l10-l50" in text
