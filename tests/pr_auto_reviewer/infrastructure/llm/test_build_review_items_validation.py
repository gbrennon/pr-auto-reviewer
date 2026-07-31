"""Tests for OllamaExploratoryChatAdapter review item validation."""

from __future__ import annotations
from pathlib import Path

import pytest

from pr_auto_reviewer.infrastructure.llm.ollama_exploratory_chat_adapter import (
    OllamaExploratoryChatAdapter,
)


class TestBuildReviewItemsValidation:
    """Tests for _build_review_items path validation."""

    def test_real_paths_are_accepted(self, tmp_path: Path) -> None:
        """Items with existing file paths are kept."""
        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "src" / "real.py").write_text("pass")
        adapter = OllamaExploratoryChatAdapter(model="test", max_retries=1, ollama_timeout=1)
        item_dicts: list[dict[str, Any]] = [
            {"file": "src/real.py", "severity": "major", "category": "bug", "description": "bad", "line": "1", "current_code": "pass", "suggested_fix": "return None"}
        ]
        result, _skip_reasons = adapter._build_review_items(item_dicts, str(tmp_path))
        assert len(result) == 1
        assert result[0].file_path == "src/real.py"

    def test_hallucinated_paths_are_skipped(self, tmp_path: Path) -> None:
        """Items referencing non-existent files are dropped with warning."""
        adapter = OllamaExploratoryChatAdapter(model="test", max_retries=1, ollama_timeout=1)
        item_dicts: list[dict[str, Any]] = [
            {"file": "nonexistent.py", "severity": "critical", "category": "security", "description": "fake", "line": "", "current_code": "", "suggested_fix": ""}
        ]
        result, _skip_reasons = adapter._build_review_items(item_dicts, str(tmp_path))
        assert len(result) == 0

    def test_mixed_real_and_hallucinated(self, tmp_path: Path) -> None:
        """Only valid items survive; numbering is sequential."""
        (tmp_path / "valid.py").write_text("ok")
        adapter = OllamaExploratoryChatAdapter(model="test", max_retries=1, ollama_timeout=1)
        item_dicts: list[dict[str, Any]] = [
            {"file": "valid.py", "severity": "minor", "category": "style", "description": "ok", "line": "", "current_code": "ok", "suggested_fix": ""},
            {"file": "fake.py", "severity": "critical", "category": "security", "description": "invented", "line": "", "current_code": "", "suggested_fix": ""},
            {"file": "valid.py", "severity": "major", "category": "bug", "description": "also ok", "line": "", "current_code": "also ok", "suggested_fix": ""},
        ]
        result, _skip_reasons = adapter._build_review_items(item_dicts, str(tmp_path))
        assert len(result) == 2
        assert result[0].number == 1
        assert result[1].number == 2

    def test_strips_ab_prefix(self, tmp_path: Path) -> None:
        """File paths with a/ or b/ prefix are normalized before validation."""
        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "src" / "lib.py").write_text("pass")
        adapter = OllamaExploratoryChatAdapter(model="test", max_retries=1, ollama_timeout=1)
        item_dicts: list[dict[str, Any]] = [
            {"file": "a/src/lib.py", "severity": "info", "category": "maintainability", "description": "nice", "line": "", "current_code": "pass", "suggested_fix": ""},
        ]
        result, _skip_reasons = adapter._build_review_items(item_dicts, str(tmp_path))
        assert len(result) == 1
        assert result[0].file_path == "src/lib.py"

    def test_empty_file_path_passes_validation(self, tmp_path: Path) -> None:
        """Items with empty file_path are not validated (cross-cutting findings)."""
        adapter = OllamaExploratoryChatAdapter(model="test", max_retries=1, ollama_timeout=1)
        item_dicts: list[dict[str, Any]] = [
            {"file": "", "severity": "major", "category": "architecture", "description": "global concern", "line": "", "current_code": "", "suggested_fix": ""},
        ]
        result, _skip_reasons = adapter._build_review_items(item_dicts, str(tmp_path))
        assert len(result) == 1

    def test_nonempty_file_path_with_empty_code_is_skipped(
        self, tmp_path: Path
    ) -> None:
        """Items with a real file path but no code evidence are dropped."""
        adapter = OllamaExploratoryChatAdapter(
            model="test", max_retries=1, ollama_timeout=1
        )
        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "src" / "empty.py").write_text("")
        item_dicts: list[dict[str, Any]] = [
            {
                "file": "src/empty.py",
                "severity": "major",
                "category": "bug",
                "description": "hallucinated finding",
                "line": "",
                "current_code": "",
                "suggested_fix": "",
            },
            {
                "file": "",
                "severity": "info",
                "category": "maintainability",
                "description": "cross-cutting is fine",
                "line": "",
                "current_code": "",
                "suggested_fix": "",
            },
        ]
        result, _skip_reasons = adapter._build_review_items(item_dicts, str(tmp_path))
        assert len(result) == 1
        assert result[0].description == "cross-cutting is fine"

    def test_empty_repo_path_disables_validation(self, tmp_path: Path) -> None:
        """Empty repo_path disables path validation."""
        adapter = OllamaExploratoryChatAdapter(model="test", max_retries=1, ollama_timeout=1)
        item_dicts: list[dict[str, Any]] = [
            {"file": "src/foo.py", "severity": "major", "category": "bug", "description": "bad", "line": "1", "current_code": "pass", "suggested_fix": "return None"},
            {"file": "src/nonexistent.py", "severity": "critical", "category": "security", "description": "fake", "line": "", "current_code": "", "suggested_fix": ""},
        ]
        result, _skip_reasons = adapter._build_review_items(item_dicts, "")
        assert len(result) == 2

    def test_keeps_crosscutting_findings_without_file_path(
        self, tmp_path: Path
    ) -> None:
        """Cross-cutting findings (no file path) are preserved."""
        adapter = OllamaExploratoryChatAdapter(model="test", max_retries=1, ollama_timeout=1)
        item_dicts: list[dict[str, Any]] = [
            {
                "file": "",
                "severity": "major",
                "category": "architecture",
                "description": "No error handling for file not found cases across the codebase",
                "line": "",
                "current_code": "",
                "suggested_fix": "",
            }
        ]
        result, _skip_reasons = adapter._build_review_items(item_dicts, str(tmp_path))
        assert len(result) == 1
        assert result[0].description == "No error handling for file not found cases across the codebase"

    def test_drops_items_with_invalid_line_numbers(self, tmp_path: Path) -> None:
        """Items with invalid line numbers are dropped."""
        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "src" / "foo.py").write_text("\n".join(["line " + str(i) for i in range(1, 11)]))
        adapter = OllamaExploratoryChatAdapter(model="test", max_retries=1, ollama_timeout=1)
        item_dicts: list[dict[str, Any]] = [
            {
                "file": "src/foo.py",
                "severity": "major",
                "category": "bug",
                "description": "valid line",
                "line": "5",
                "current_code": "line 5",
                "suggested_fix": "fixed",
            },
            {
                "file": "src/foo.py",
                "severity": "critical",
                "category": "security",
                "description": "invalid line",
                "line": "999",
                "current_code": "made up",
                "suggested_fix": "",
            },
        ]
        result, _skip_reasons = adapter._build_review_items(item_dicts, str(tmp_path))
        assert len(result) == 1
        assert result[0].description == "valid line"

    def test_drops_items_with_mismatched_code(self, tmp_path: Path) -> None:
        """Items whose current_code doesn't match file content are dropped."""
        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "src" / "foo.py").write_text("def foo():\n    return 42")
        adapter = OllamaExploratoryChatAdapter(model="test", max_retries=1, ollama_timeout=1)
        item_dicts: list[dict[str, Any]] = [
            {
                "file": "src/foo.py",
                "severity": "major",
                "category": "bug",
                "description": "correct code",
                "line": "1",
                "current_code": "def foo():",
                "suggested_fix": "def foo() -> int:",
            },
            {
                "file": "src/foo.py",
                "severity": "critical",
                "category": "security",
                "description": "hallucinated code",
                "line": "1",
                "current_code": "def bar():",
                "suggested_fix": "",
            },
        ]
        result, _skip_reasons = adapter._build_review_items(item_dicts, str(tmp_path))
        assert len(result) == 1
        assert result[0].description == "correct code"