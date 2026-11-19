from pathlib import Path

class TestReviewQualityContract:
    """Review prompts constrain findings to verified implementation gaps."""

    @staticmethod
    def _root() -> Path:
        return Path(__file__).parents[4]

    def _prompt(self, name: str) -> str:
        return (
            self._root()
            / "src"
            / "pr_auto_reviewer"
            / "infrastructure"
            / "fragments"
            / "content"
            / "universal"
            / name
        ).read_text()

    def _schema(self) -> str:
        return (
            self._root()
            / "src"
            / "pr_auto_reviewer"
            / "infrastructure"
            / "templates"
            / "conversation"
            / "_schemas.j2"
        ).read_text()

    def test_system_prompt_requires_intent_and_evidence_for_gaps(self) -> None:
        content = self._prompt("reviewer-system-prompt.md")

        assert "IMPLEMENTATION COMPLETENESS" in content
        assert "Confirmed implementation gap" in content
        assert "Likely gap" in content
        assert "Unconfirmed observation" in content
        assert "Safe fallbacks such as" in content
        assert "direct, calm, and evidence-based" in content

    def test_branch_phase_rejects_ambiguous_gaps_as_defects(self) -> None:
        content = self._prompt("bug-hunt-branch.md")

        assert "implementation-completeness pass" in content
        assert "intended behavior is" in content
        assert "explicit and the implementation" in content
        assert "ambiguous intent is" in content
        assert "Implementation gap —" in content

    def test_verdict_schema_requires_grounded_gap_descriptions(self) -> None:
        content = self._schema()

        assert "intended behavior, observed behavior, missing connection" in content
        assert "ambiguous gaps as non-blocking suggestions or omit them" in content
        assert "never claim a standard-library or framework operation is unsafe" in content
