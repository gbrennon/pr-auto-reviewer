"""Tests for OllamaExploratoryChatAdapter file listing extraction."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.llm.ollama.ollama_exploratory_chat_adapter import (
    OllamaExploratoryChatAdapter,
)


class TestExtractFileListing:
    """Tests for _extract_file_listing static method."""

    def test_extracts_files_from_diff_section(self) -> None:
        """Extract file list from diff section."""
        diff_content = "## Diff\n--- a/src/foo.py\n+++ b/src/foo.py\n@@ -1,3 +1,4 @@\n def foo():\n     pass\n\n+def bar():\n+    pass\n--- a/src/baz.py\n+++ b/src/baz.py\n@@ -1,3 +1,4 @@\n def baz():\n     pass\n"
        result = OllamaExploratoryChatAdapter._extract_file_listing(diff_content)
        assert result == ["src/baz.py", "src/foo.py"]

    def test_ignores_non_diff_lines(self) -> None:
        """Ignore lines that don't match diff markers."""
        mixed_content = (
            "Some random text\n"
            "## Diff\n"
            "More random text\n"
            "--- a/src/foo.py\n"
            "+++ b/src/foo.py\n"
            "Still random\n"
            "--- a/src/baz.py\n"
            "+++ b/src/baz.py\n"
        )
        result = OllamaExploratoryChatAdapter._extract_file_listing(mixed_content)
        assert result == ["src/baz.py", "src/foo.py"]

    def test_handles_empty_input(self) -> None:
        """Return empty list for empty input."""
        result = OllamaExploratoryChatAdapter._extract_file_listing("")
        assert result == []

    def test_handles_no_diff_markers(self) -> None:
        """Return empty list when no diff markers found."""
        result = OllamaExploratoryChatAdapter._extract_file_listing("No diff markers here")
        assert result == []