from ._helpers import *


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

