from ._helpers import *


class TestBudgetAwarePromptBuilder:
    """Tests for budget-aware PromptBuilder with max_tokens > 0."""

    def test_legacy_mode_unlimited_when_max_tokens_zero(self, _diff, _context):
        """Legacy mode (max_tokens=0) includes everything unchanged."""
        result = PromptBuilder(max_tokens=0).build(_diff, _context)
        assert "+added line" in result
        assert "clean-architecture" in result
        assert "Use type hints" in result
        assert "src/" in result

    def test_trims_large_diff_when_over_budget(self, _context):
        """With a very tight budget, the diff gets truncated."""
        large_diff = "\n".join(
            f"diff --git a/f{i}.py b/f{i}.py\n--- a/f{i}.py\n+++ b/f{i}.py\n@@ -1 +1 @@\n-old\n+new{i}\n"
            for i in range(50)
        )
        diff = PullRequestDiff(
            pr_id=PullRequestId(repository="o/r", number=1),
            head_sha=CommitSha(value="abc"),
            diff_content=large_diff,
        )
        result = PromptBuilder(max_tokens=100).build(diff, _context)
        assert "Senior Principal Software Engineer" in result

    def test_compact_template_is_shorter(self, _diff, _context):
        """Compact template produces a shorter prompt than the full one."""
        full = PromptBuilder(use_compact_template=False).build(_diff, _context)
        compact = PromptBuilder(use_compact_template=True).build(_diff, _context)
        assert len(compact) < len(full)
        assert "Senior Principal" in compact

    def test_file_contents_trimmed_when_many_files(self, _context):
        """When file_contents has many files, only max_files are kept."""
        contents = {f"f{i}.py": f"print({i})" for i in range(20)}
        diff = PullRequestDiff(
            pr_id=PullRequestId(repository="o/r", number=1),
            head_sha=CommitSha(value="abc"),
            diff_content="+new line",
            file_contents=contents,
        )
        result = PromptBuilder(max_tokens=32000, max_files=3).build(diff, _context)
        count = result.count("### f")
        assert count <= 3, f"Expected ≤3 files, got {count}"

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

