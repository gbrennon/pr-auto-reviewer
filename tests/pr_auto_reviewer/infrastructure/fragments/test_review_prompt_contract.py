from pathlib import Path

class TestReviewPromptContract:
    """Review prompts require grounded completeness findings."""

    @staticmethod
    def _content_path(name: str) -> Path:
        return (
            Path(__file__).parents[4]
            / "src"
            / "pr_auto_reviewer"
            / "infrastructure"
            / "fragments"
            / "content"
            / "universal"
            / name
        )

    def test_system_prompt_requires_verified_implementation_gaps(self) -> None:
        content = self._content_path("reviewer-system-prompt.md").read_text()

        assert "IMPLEMENTATION COMPLETENESS" in content
        assert "Confirmed implementation gap" in content
        assert "Safe fallbacks such as" in content
        assert "direct, calm, and evidence-based" in content

    def test_branch_phase_checks_reachable_behavior_and_ambiguity(self) -> None:
        content = self._content_path("bug-hunt-branch.md").read_text()

        assert "implementation-completeness pass" in content
        assert "public entry points" in content
        assert "ambiguous intent" in content
        assert "Implementation gap —" in content

    def test_verifier_requires_evidence_for_affirmative_results(self) -> None:
        content = self._content_path("verify-findings.md").read_text()

        assert "evidence confirms the described defect" in content
        assert "defensive-only" in content
        assert "set `verified` to `false`" in content
