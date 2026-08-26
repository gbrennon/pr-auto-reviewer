from ._helpers import *


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

