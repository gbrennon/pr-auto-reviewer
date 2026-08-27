from ._helpers import *


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

