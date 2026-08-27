from ._helpers import *


class TestPromptBuilder:

    def test_build_includes_diff_content(self, _diff, _context):
        result = PromptBuilder().build(_diff, _context)
        assert "+added line" in result

    def test_build_includes_architecture_hint(self, _diff, _context):
        result = PromptBuilder().build(_diff, _context)
        assert "clean-architecture" in result

    def test_build_includes_repository_structure(self, _diff, _context):
        result = PromptBuilder().build(_diff, _context)
        assert "src/" in result

    def test_build_includes_conventions(self, _diff, _context):
        result = PromptBuilder().build(_diff, _context)
        assert "Use type hints" in result

    def test_build_includes_response_format_json(self, _diff, _context):
        result = PromptBuilder().build(_diff, _context)
        assert '"issues"' in result

    def test_build_omits_architecture_section_when_empty(self, _diff):
        context = RepositoryContext(architecture_hint="")
        result = PromptBuilder().build(_diff, context)
        assert "## Architecture" not in result

    def test_build_omits_conventions_when_none(self, _diff):
        context = RepositoryContext(architecture_hint="", conventions=None)
        result = PromptBuilder().build(_diff, context)
        assert "## Project conventions" not in result

    def test_build_omits_structure_when_none(self, _diff):
        context = RepositoryContext(
            architecture_hint="", repository_structure=None,
        )
        result = PromptBuilder().build(_diff, context)
        assert "## Repository structure" not in result

    def test_build_uses_diff_conventions_fallback(self):
        diff = PullRequestDiff(
            pr_id=PullRequestId(repository="o/r", number=1),
            head_sha=CommitSha(value="abc"),
            diff_content="diff",
            conventions="fallback conventions",
        )
        ctx = RepositoryContext(architecture_hint="", conventions=None)
        result = PromptBuilder().build(diff, ctx)
        assert "fallback conventions" in result

    def test_build_uses_diff_structure_fallback(self):
        diff = PullRequestDiff(
            pr_id=PullRequestId(repository="o/r", number=1),
            head_sha=CommitSha(value="abc"),
            diff_content="diff",
            repository_structure="fallback structure",
        )
        ctx = RepositoryContext(
            architecture_hint="", repository_structure=None,
        )
        result = PromptBuilder().build(diff, ctx)
        assert "fallback structure" in result

    def test_build_starts_with_system_prompt(self, _diff, _context):
        result = PromptBuilder().build(_diff, _context)
        assert "Senior Principal Software Engineer" in result

    def test_build_ends_with_remember_message(self, _diff, _context):
        result = PromptBuilder().build(_diff, _context)
        assert result.rstrip().endswith("not to undo them.")

    def test_build_includes_file_contents_when_present(self, _context):
        diff = PullRequestDiff(
            pr_id=PullRequestId(repository="o/r", number=1),
            head_sha=CommitSha(value="abc"),
            diff_content="+new line",
            file_contents={"scripts/install.sh": "#!/usr/bin/env bash\nset -euo pipefail"},
        )
        result = PromptBuilder().build(diff, _context)
        assert "## Full File Contents" in result
        assert "### scripts/install.sh" in result
        assert "#!/usr/bin/env bash" in result

    def test_build_omits_file_contents_section_when_empty(self, _diff, _context):
        result = PromptBuilder().build(_diff, _context)
        assert "## Full File Contents" not in result

    def test_build_includes_anti_hallucination_guidelines(self, _diff, _context):
        result = PromptBuilder().build(_diff, _context)
        assert "missing shebang" in result
        assert "hallucination" in result

    def test_build_file_contents_with_multiple_files(self, _context):
        diff = PullRequestDiff(
            pr_id=PullRequestId(repository="o/r", number=1),
            head_sha=CommitSha(value="abc"),
            diff_content="+new line",
            file_contents={
                "a.py": "print('hello')",
                "b.py": "print('world')",
            },
        )
        result = PromptBuilder().build(diff, _context)
        assert "### a.py" in result
        assert "### b.py" in result
        assert "print('hello')" in result
        assert "print('world')" in result

    @pytest.fixture
    def _diff(self):
        return PullRequestDiff(
            pr_id=PullRequestId(repository="o/r", number=1),
            head_sha=CommitSha(value="abc"),
            diff_content="+added line\n-removed line",
        )

    @pytest.fixture
    def _context(self):
        return RepositoryContext(
            architecture_hint="clean-architecture",
            repository_structure="src/\n  main.py",
            conventions="Use type hints",
        )

