import pytest
from pr_auto_reviewer.infrastructure.llm.diff_analyzer import DiffAnalyzer

@pytest.fixture
def sample_diff():
    return (
        "diff --git a/foo.txt b/foo.txt\n"
        "index 83db48f..f735c60 100644\n"
        "--- a/foo.txt\n"
        "+++ b/foo.txt\n"
        "@@ -1 +2,3 @@\n"
        " line1\n"
        "+added line A\n"
        "+added line B\n"
        "-removed line\n"
    )

@pytest.fixture
def large_file_contents():
    return "\n".join(f"line {i}" for i in range(1, 201))

def test_parse_diff_hunks_and_extract_context(sample_diff, large_file_contents):
    da = DiffAnalyzer()
    hunks = da.parse_diff_hunks(sample_diff)
    assert "foo.txt" in hunks
    assert hunks["foo.txt"][0][0] == 2
    assert hunks["foo.txt"][0][1] == 4

    context = da.extract_context_around_hunks(large_file_contents, hunks["foo.txt"], context_lines=2, max_chars=500)
    assert "    1:" in context or "1:" in context
    assert "..." in context or "line" in context

def test_classify_and_annotate():
    da = DiffAnalyzer()
    deleted_chunk = (
        "diff --git a/old.txt b/old.txt\n"
        "deleted file mode 100644\n"
        "--- a/old.txt\n"
        "+++ /dev/null\n"
    )
    added_chunk = (
        "diff --git a/new.txt b/new.txt\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        "+++ b/new.txt\n"
    )
    modified_chunk = (
        "diff --git a/mod.txt b/mod.txt\n"
        "--- a/mod.txt\n"
        "+++ b/mod.txt\n"
        "@@ -1 +1,2 @@\n"
        "+new\n"
    )
    raw = deleted_chunk + added_chunk + modified_chunk
    annotated = da.annotate_diff_with_markers(raw)
    assert "[DELETED] old.txt" in annotated
    assert "[ADDED] new.txt" in annotated
    assert "[MODIFIED] mod.txt" in annotated

def test_trim_diff_by_file_boundaries_success_and_failure(sample_diff):
    da = DiffAnalyzer()
    raw = sample_diff * 10

    result_ok = da.trim_diff_by_file_boundaries(raw, max_tokens=10000)
    assert result_ok == raw

    result_trimmed = da.trim_diff_by_file_boundaries(raw, max_tokens=1)
    assert result_trimmed != raw
    assert result_trimmed.endswith("\n")

def test_trim_file_contents_to_limits(sample_diff, large_file_contents):
    da = DiffAnalyzer()
    file_contents = {"foo.txt": large_file_contents, "other.txt": "small content"}
    trimmed = da.trim_file_contents_to_limits(file_contents, sample_diff, max_files=2, max_chars_per_file=100)
    assert "foo.txt" in trimmed
    assert "other.txt" in trimmed
    assert "(file truncated" in trimmed["foo.txt"] or len(trimmed["foo.txt"]) <= 1000

def test_trim_repo_structure_to_lines():
    da = DiffAnalyzer()
    structure = "\n".join(f"entry {i}" for i in range(200))
    trimmed = da.trim_repo_structure_to_lines(structure, max_lines=50)
    assert "omitted" in trimmed
    assert trimmed.count("\n") <= 51
