from ._helpers import *


class TestRunSnippet:
    """Exercises run_snippet code execution."""

    def test_executes_python_and_returns_output(self, repo) -> None:
        (repo / "hello.py").write_text("print(42)")
        service = _service(repo)

        result = service.run_snippet("import hello")

        assert result["status"] == "ok"
        assert "42" in result["stdout"]
        assert result["exit_code"] == 0

    def test_reports_syntax_error(self, repo) -> None:
        service = _service(repo)

        result = service.run_snippet("def broken(")

        assert result["status"] == "error"
        assert result["exit_code"] != 0
        assert "SyntaxError" in result["stderr"]

    def test_reports_runtime_exception_without_raising(self, repo) -> None:
        service = _service(repo)

        result = service.run_snippet("raise RuntimeError('boom')")

        assert result["status"] == "error"
        assert result["exit_code"] != 0
        assert "RuntimeError: boom" in result["stderr"]
        assert "RuntimeError: boom" in result["error"]
