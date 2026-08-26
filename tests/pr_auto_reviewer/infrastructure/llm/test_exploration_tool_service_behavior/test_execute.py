from ._helpers import *


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

    def test_execute_tool_when_file_path_alias_then_reads_file(
        self, repo,
    ) -> None:
        tool = ToolCall(
            tool_name="read_file",
            arguments={"file_path": "src/app.py"},
        )

        result = _service(repo).execute_tool(tool)

        assert result.status == "ok"
        assert result.data["content"].startswith("line1")

    def test_execute_tool_when_path_alias_then_reads_file(
        self, repo,
    ) -> None:
        tool = ToolCall(
            tool_name="read_file",
            arguments={"path": "src/app.py"},
        )

        result = _service(repo).execute_tool(tool)

        assert result.status == "ok"

    def test_execute_tool_when_single_unknown_key_then_fallback(
        self, repo,
    ) -> None:
        tool = ToolCall(
            tool_name="read_file",
            arguments={"target": "src/app.py"},
        )

        result = _service(repo).execute_tool(tool)

        assert result.status == "ok"

    def test_execute_tool_when_empty_args_then_error(self, repo) -> None:
        tool = ToolCall(tool_name="read_file", arguments={})

        result = _service(repo).execute_tool(tool)

        assert result.status == "error"

