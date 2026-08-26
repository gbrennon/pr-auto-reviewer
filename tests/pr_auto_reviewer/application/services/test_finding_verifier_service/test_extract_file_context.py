from ._helpers import *


class TestExtractFileContext:
    """Surrounding-context extraction for a code snippet."""

    def _verifier(self, mock_chat_port, mock_tool_factory) -> FindingVerifierService:
        return FindingVerifierService(
            mock_chat_port, "verify {findings}", mock_tool_factory
        )

    def test_returns_error_message_when_file_unreadable(
        self, tmp_path, mock_chat_port, mock_tool_factory,
    ) -> None:
        text = self._verifier(
            mock_chat_port, mock_tool_factory
        )._extract_file_context(tmp_path / "missing.txt", "x")

        assert text == "(file could not be read)"

    def test_returns_head_when_snippet_empty(
        self, tmp_path, mock_chat_port, mock_tool_factory,
    ) -> None:
        path = tmp_path / "a.txt"
        path.write_text("line1\nline2\n")

        text = self._verifier(
            mock_chat_port, mock_tool_factory
        )._extract_file_context(path, "")

        assert text == "line1\nline2\n"

    def test_returns_head_when_snippet_blank(
        self, tmp_path, mock_chat_port, mock_tool_factory,
    ) -> None:
        path = tmp_path / "a.txt"
        path.write_text("content")

        text = self._verifier(
            mock_chat_port, mock_tool_factory
        )._extract_file_context(path, "   \n ")

        assert text == "content"

    def test_returns_window_around_exact_line(
        self, tmp_path, mock_chat_port, mock_tool_factory,
    ) -> None:
        path = tmp_path / "a.txt"
        path.write_text("\n".join(f"line{i}" for i in range(100)))

        text = self._verifier(
            mock_chat_port, mock_tool_factory
        )._extract_file_context(path, "line50")

        assert "line50" in text
        assert "line39" not in text
        assert "line99" in text

    def test_falls_back_to_substring_match(
        self, tmp_path, mock_chat_port, mock_tool_factory,
    ) -> None:
        path = tmp_path / "a.txt"
        path.write_text("alpha\nbeta gamma\nomega\n")

        text = self._verifier(
            mock_chat_port, mock_tool_factory
        )._extract_file_context(path, "gamma")

        assert "beta gamma" in text

    def test_returns_head_when_no_match(
        self, tmp_path, mock_chat_port, mock_tool_factory,
    ) -> None:
        path = tmp_path / "a.txt"
        path.write_text("alpha\nbeta\n")

        text = self._verifier(
            mock_chat_port, mock_tool_factory
        )._extract_file_context(path, "zeta")

        assert text == "alpha\nbeta\n"

