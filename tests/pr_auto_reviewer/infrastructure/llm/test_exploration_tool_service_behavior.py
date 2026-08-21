"""Behavioral tests for ExplorationToolService against a real temporary repo."""

import pytest

from pr_auto_reviewer.domain.agent.tool_call import ToolCall
from pr_auto_reviewer.infrastructure.llm.exploration_tool_service import (
    ExplorationToolService,
)


@pytest.fixture
def repo(tmp_path):
    """A temporary repo with source files, a binary, and git history."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("\n".join(f"line{i}" for i in range(1, 21)))
    (src / "main.py").write_text("import app\n")
    (tmp_path / "data.bin").write_bytes(b"\xff\xfe\x00\x01")
    return tmp_path


@pytest.fixture
def git_repo(repo, monkeypatch):
    """The repo initialized as a git worktree with one commit."""
    import subprocess

    monkeypatch.setenv("GIT_AUTHOR_NAME", "test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.com")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    return repo


def _service(repo):
    return ExplorationToolService(repo)


class TestConstruction:
    """Exercises __init__ validation."""

    def test_init_when_empty_path_then_raises(self) -> None:
        with pytest.raises(ValueError):
            ExplorationToolService("")

    def test_init_when_missing_dir_then_raises(self, tmp_path) -> None:
        with pytest.raises(ValueError):
            ExplorationToolService(tmp_path / "nope")

    def test_init_when_valid_then_sets_root(self, repo) -> None:
        service = _service(repo)

        assert service._repo_root == repo.resolve()
        assert service._changed_files == []


class TestReadFile:
    """Exercises read_file resolution and content slicing."""

    def test_read_when_file_then_returns_content(self, repo) -> None:
        result = _service(repo).read_file("src/app.py")

        assert result["status"] == "ok"
        assert result["content"].startswith("line1")

    def test_read_when_line_range_then_slices(self, repo) -> None:
        result = _service(repo).read_file("src/app.py L2-L4")

        assert result["content"] == "line2\nline3\nline4"

    def test_read_when_single_line_range_then_slices(self, repo) -> None:
        result = _service(repo).read_file("src/app.py L5-L5")

        assert result["content"] == "line5"

    def test_read_when_open_range_then_to_end(self, repo) -> None:
        result = _service(repo).read_file("src/app.py L17")

        assert result["content"].endswith("line20")

    def test_read_when_path_traversal_then_blocked(self, repo) -> None:
        result = _service(repo).read_file("../secret")

        assert result["status"] == "error"
        assert "blocked" in result["error"]

    def test_read_when_missing_file_then_error(self, repo) -> None:
        result = _service(repo).read_file("src/missing.py")

        assert result["status"] == "error"
        assert "File not found" in result["error"]

    def test_read_when_binary_then_error(self, repo) -> None:
        result = _service(repo).read_file("data.bin")

        assert result["status"] == "error"
        assert "Binary file" in result["error"]

    def test_read_when_out_of_range_line_then_error(self, repo) -> None:
        result = _service(repo).read_file("src/app.py L99")

        assert result["status"] == "error"
        assert "out of range" in result["error"]

    def test_read_when_oversized_then_error(self, repo) -> None:
        (repo / "big.py").write_bytes(b"x" * (100 * 1024 + 1))

        result = _service(repo).read_file("big.py")

        assert result["status"] == "error"
        assert "byte limit" in result["error"]


class TestSearchCodebase:
    """Exercises grep-based search."""

    def test_search_when_hits_then_returns_matches(self, repo) -> None:
        result = _service(repo).search_codebase("line3")

        assert result["status"] == "ok"
        assert any(hit["line"] == 3 for hit in result["hits"])
        assert result["truncated"] is False

    def test_search_when_no_match_then_empty(self, repo) -> None:
        result = _service(repo).search_codebase("zzz_none")

        assert result["status"] == "ok"
        assert result["hits"] == []

    def test_search_when_empty_pattern_then_error(self, repo) -> None:
        result = _service(repo).search_codebase("  ")

        assert result["status"] == "error"
        assert "Empty" in result["error"]


class TestListDirectory:
    """Exercises directory listing."""

    def test_list_when_directory_then_entries(self, repo) -> None:
        result = _service(repo).list_directory("src")

        assert result["status"] == "ok"
        names = {entry["name"] for entry in result["entries"]}
        assert {"app.py", "main.py"} <= names

    def test_list_when_root_dot_then_works(self, repo) -> None:
        result = _service(repo).list_directory(".")

        assert result["status"] == "ok"
        assert any(entry["name"] == "src" for entry in result["entries"])

    def test_list_when_not_a_directory_then_error(self, repo) -> None:
        result = _service(repo).list_directory("src/app.py")

        assert result["status"] == "error"
        assert "Not a directory" in result["error"]

    def test_list_when_traversal_then_blocked(self, repo) -> None:
        result = _service(repo).list_directory("../etc")

        assert result["status"] == "error"


class TestRunGit:
    """Exercises read-only git execution."""

    def test_git_when_allowed_subcommand_then_output(self, git_repo) -> None:
        result = _service(git_repo).run_git("status --short")

        assert result["status"] == "ok"
        assert result["subcommand"] == "status"

    def test_git_when_log_then_commits(self, git_repo) -> None:
        result = _service(git_repo).run_git("log --oneline")

        assert result["status"] == "ok"
        assert "init" in result["output"]

    def test_git_when_disallowed_subcommand_then_error(self, git_repo) -> None:
        result = _service(git_repo).run_git("push origin main")

        assert result["status"] == "error"
        assert "not allowed" in result["error"]

    def test_git_when_empty_args_then_error(self, git_repo) -> None:
        result = _service(git_repo).run_git("  ")

        assert result["status"] == "error"
        assert "Empty" in result["error"]

    def test_git_when_fails_then_error(self, repo) -> None:
        result = _service(repo).run_git("show HEAD")

        assert result["status"] == "error"


class TestExecute:
    """Exercises the dispatcher."""

    def test_execute_when_dict_args_then_normalized(self, repo) -> None:
        result = _service(repo).execute("read_file", {"path": "src/app.py"})

        assert result["status"] == "ok"

    def test_execute_when_search_dispatch(self, repo) -> None:
        result = _service(repo).execute("search_codebase", "line3")

        assert result["status"] == "ok"

    def test_execute_when_list_dispatch(self, repo) -> None:
        result = _service(repo).execute("list_directory", {"dir": "src"})

        assert result["status"] == "ok"

    def test_execute_when_git_dispatch(self, repo) -> None:
        result = _service(repo).execute("run_git", {"args": "banana"})

        assert result["status"] == "error"

    def test_execute_when_changed_files_dispatch(self, repo) -> None:
        result = _service(repo).execute("get_changed_files", "")

        assert result["status"] == "ok"
        assert result["files"] == []

    def test_execute_when_unknown_then_error(self, repo) -> None:
        result = _service(repo).execute("nope", "x")

        assert result["status"] == "error"
        assert "Unknown operation" in result["error"]

    def test_execute_tool_when_ok_then_result(self, repo) -> None:
        tool = ToolCall(tool_name="read_file", arguments={"args": "src/app.py"})

        result = _service(repo).execute_tool(tool)
        data = result.data

        assert result.status == "ok"
        assert data is not None
        assert data["content"].startswith("line1")

    def test_execute_tool_when_error_then_error_result(self, repo) -> None:
        tool = ToolCall(tool_name="read_file", arguments={"args": "../x"})

        result = _service(repo).execute_tool(tool)

        assert result.status == "error"
        assert result.error is not None


class TestChangedFiles:
    """Exercises the changed-files report."""

    def test_get_changed_files_when_none_then_empty(self, repo) -> None:
        result = _service(repo).get_changed_files()

        assert result == {"status": "ok", "files": []}

    def test_get_changed_files_when_provided_then_returns(self, repo) -> None:
        result = ExplorationToolService(repo, changed_files=["a.py", "b.py"]).get_changed_files()

        assert result == {"status": "ok", "files": ["a.py", "b.py"]}

    def test_resolve_safe_when_absolute_inside_repo_then_allowed(self, repo) -> None:
        service = _service(repo)
        path = service._resolve_safe(str(repo / "src" / "app.py"))

        assert path is not None
        assert path.name == "app.py"