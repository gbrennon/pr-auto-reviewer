import pytest
from pr_auto_reviewer.infrastructure.llm.prompt_builder import (
    PromptBuilder,
    PromptBudget,
    _trim_diff,
    _trim_file_contents,
    _trim_repo_structure,
    _parse_diff_hunks,
    _extract_surrounding_context,
    _annotate_diff,
)
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.repository_context import (
    RepositoryContext,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha


class TestPromptBuilder:

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


# --- PromptBudget tests ------------------------------------------------------


class TestPromptBudget:
    def test_estimate_tokens_rough_heuristic(self):
        """1 token ≈ 4 characters."""
        text = "a" * 100
        assert PromptBudget.estimate_tokens(text) == 25

    def test_consume_increases_consumed(self):
        budget = PromptBudget(max_tokens=100)
        budget.consume("a" * 40)
        assert budget._consumed == 10
        assert budget.remaining_tokens == 90

    def test_would_fit_returns_true_when_room(self):
        budget = PromptBudget(max_tokens=100)
        assert budget.would_fit("a" * 200) is True  # 50 tokens
        assert budget.would_fit("a" * 500) is False  # 125 tokens

    def test_try_consume_consumes_if_fits(self):
        budget = PromptBudget(max_tokens=50)
        assert budget.try_consume("a" * 100) is True  # 25 tokens
        assert budget.try_consume("a" * 200) is False  # 50 tokens would exceed
        assert budget._consumed == 25

    def test_remaining_tokens_never_negative(self):
        budget = PromptBudget(max_tokens=10)
        budget.consume("a" * 100)  # 25 tokens consumed, but max is 10
        assert budget.remaining_tokens == 0


# --- Diff annotation tests ---------------------------------------------------


class TestAnnotateDiff:
    def test_annotates_added_file(self):
        diff = (
            "diff --git a/new.py b/new.py\n"
            "new file mode 100644\n"
            "index 0000000..abc\n"
            "--- /dev/null\n"
            "+++ b/new.py\n"
            "@@ -0,0 +1 @@\n"
            "+print('hello')\n"
        )
        result = _annotate_diff(diff)
        assert "[ADDED] new.py" in result
        assert "Review its content" in result

    def test_annotates_deleted_file(self):
        diff = (
            "diff --git a/old.py b/old.py\n"
            "deleted file mode 100644\n"
            "--- a/old.py\n"
            "+++ /dev/null\n"
            "@@ -1 +0,0 @@\n"
            "-print('bye')\n"
        )
        result = _annotate_diff(diff)
        assert "[DELETED] old.py" in result
        assert "being removed" in result

    def test_annotates_modified_file(self):
        diff = (
            "diff --git a/file.py b/file.py\n"
            "index abc..def 100644\n"
            "--- a/file.py\n"
            "+++ b/file.py\n"
            "@@ -1 +1,2 @@\n"
            " unchanged\n"
            "+new line\n"
        )
        result = _annotate_diff(diff)
        assert "[MODIFIED] file.py" in result


# --- Diff truncation tests ---------------------------------------------------


class TestTrimDiff:
    def test_returns_unchanged_when_under_budget(self):
        diff = (
            "diff --git a/a.py b/a.py\n"
            "--- a/a.py\n"
            "+++ b/a.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
        )
        result = _trim_diff(diff, max_tokens=500)
        assert result == diff

    def test_truncates_large_diff_at_boundaries(self):
        diff = ""
        for i in range(3):
            diff += (
                f"diff --git a/file{i}.py b/file{i}.py\n"
                f"--- a/file{i}.py\n"
                f"+++ b/file{i}.py\n"
                f"@@ -1 +1 @@\n"
                f"-old{i}\n"
                f"+new{i}\n"
            )
        result = _trim_diff(diff, max_tokens=20)
        assert "diff --git" in result
        assert len(result) < len(diff)


# --- File content truncation tests -------------------------------------------


class TestTrimFileContents:
    def test_returns_empty_for_empty_input(self):
        assert _trim_file_contents({}, "") == {}

    def test_limits_number_of_files(self):
        contents = {f"f{i}.py": f"content{i}" for i in range(20)}
        result = _trim_file_contents(contents, "", max_files=3)
        assert len(result) <= 3

    def test_extracts_context_around_hunks(self):
        file_contents = {
            "main.py": "\n".join(
                f"line {i}" for i in range(1, 101)
            )
        }
        diff = (
            "diff --git a/main.py b/main.py\n"
            "--- a/main.py\n"
            "+++ b/main.py\n"
            "@@ -50,3 +50,4 @@\n"
            " line 50\n"
            " line 51\n"
            "-line 52\n"
            "+line 52 modified\n"
            " line 53\n"
        )
        result = _trim_file_contents(file_contents, diff, max_chars_per_file=5000)
        assert "main.py" in result
        content = result["main.py"]
        assert "line 50" in content
        assert "line 53" in content


# --- Repo structure truncation tests -----------------------------------------


class TestTrimRepoStructure:
    def test_unchanged_when_under_limit(self):
        structure = "\n".join(f"file{i}.py" for i in range(5))
        result = _trim_repo_structure(structure, max_lines=10)
        assert result == structure

    def test_truncates_when_over_limit(self):
        structure = "\n".join(f"file{i}.py" for i in range(200))
        result = _trim_repo_structure(structure, max_lines=50)
        assert "..." in result
        assert result.count("\n") < 100


# --- Budget-aware PromptBuilder tests ----------------------------------------


class TestBudgetAwarePromptBuilder:
    """Tests for budget-aware PromptBuilder with max_tokens > 0."""

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
