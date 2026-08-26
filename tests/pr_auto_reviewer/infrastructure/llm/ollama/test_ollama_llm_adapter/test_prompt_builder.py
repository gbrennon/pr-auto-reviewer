from ._helpers import *


class TestPromptBuilder:
    """Tests for PromptBuilder."""

    def test_build_includes_diff(
        self, sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        prompt_builder: PromptBuilder,
    ) -> None:
        """Prompt includes the diff content."""
        prompt = prompt_builder.build(sample_diff, sample_context)
        assert "diff --git" in prompt
        assert ".env.example" in prompt

    def test_build_includes_architecture_hint(
        self, sample_diff: PullRequestDiff, prompt_builder: PromptBuilder,
    ) -> None:
        """Prompt includes architecture hint when provided."""
        context = RepositoryContext(
            architecture_hint="Layered architecture",
            conventions="",
            repository_structure="",
        )
        prompt = prompt_builder.build(sample_diff, context)
        assert "Layered architecture" in prompt

    def test_build_includes_conventions(
        self, sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        prompt_builder: PromptBuilder,
    ) -> None:
        """Prompt includes conventions when provided."""
        diff = PullRequestDiff(
            pr_id=None, head_sha=None,
            diff_content="", conventions="Use type hints"
        )
        prompt = prompt_builder.build(diff, sample_context)
        assert "Use type hints" in prompt

    def test_build_includes_repo_structure(
        self, sample_diff: PullRequestDiff, prompt_builder: PromptBuilder,
    ) -> None:
        """Prompt includes repository structure when provided."""
        context = RepositoryContext(
            architecture_hint="",
            conventions="",
            repository_structure="src/\n  main.py",
        )
        prompt = prompt_builder.build(sample_diff, context)
        assert "src/" in prompt

    def test_build_uses_json_format(
        self, sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        prompt_builder: PromptBuilder,
    ) -> None:
        """Prompt requests JSON output format."""
        prompt = prompt_builder.build(sample_diff, sample_context)
        assert '"issues"' in prompt
        assert '"severity"' in prompt
        assert '"category"' in prompt

