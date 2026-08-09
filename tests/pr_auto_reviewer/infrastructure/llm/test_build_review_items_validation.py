"""Tests for ReviewItemFactory review item validation."""

from __future__ import annotations
from pathlib import Path
from typing import Any

from pr_auto_reviewer.domain.services.review_item_factory import (
    ReviewItemFactory,
)


class TestBuildReviewItemsValidation:
    """Tests for ReviewItemFactory.create path validation."""

    def test_real_paths_are_accepted(self, tmp_path: Path) -> None:
        """Items with existing file paths are kept."""
        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "src" / "real.py").write_text("pass")
        item_dicts: list[dict[str, Any]] = [
            {"file": "src/real.py", "severity": "major", "category": "bug", "description": "bad", "line": "1", "current_code": "pass", "suggested_fix": "return None"}
        ]
        result, _skip_reasons = ReviewItemFactory().create(item_dicts, str(tmp_path))
        assert len(result) == 1
        assert result[0].file_path == "src/real.py"

    def test_hallucinated_paths_are_skipped(self, tmp_path: Path) -> None:
        """Items referencing non-existent files are dropped with warning."""
        item_dicts: list[dict[str, Any]] = [
            {"file": "nonexistent.py", "severity": "critical", "category": "security", "description": "fake", "line": "", "current_code": "", "suggested_fix": ""}
        ]
        result, _skip_reasons = ReviewItemFactory().create(item_dicts, str(tmp_path))
        assert len(result) == 0

    def test_mixed_real_and_hallucinated(self, tmp_path: Path) -> None:
        """Only valid items survive; numbering is sequential."""
        (tmp_path / "valid.py").write_text("ok")
        item_dicts: list[dict[str, Any]] = [
            {"file": "valid.py", "severity": "minor", "category": "style", "description": "ok", "line": "", "current_code": "ok", "suggested_fix": ""},
            {"file": "fake.py", "severity": "critical", "category": "security", "description": "invented", "line": "", "current_code": "", "suggested_fix": ""},
            {"file": "valid.py", "severity": "major", "category": "bug", "description": "also ok", "line": "", "current_code": "also ok", "suggested_fix": ""},
        ]
        result, _skip_reasons = ReviewItemFactory().create(item_dicts, str(tmp_path))
        assert len(result) == 2
        assert result[0].number == 1
        assert result[1].number == 2

    def test_strips_ab_prefix(self, tmp_path: Path) -> None:
        """File paths with a/ or b/ prefix are normalized before validation."""
        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "src" / "lib.py").write_text("pass")
        item_dicts: list[dict[str, Any]] = [
            {"file": "a/src/lib.py", "severity": "info", "category": "maintainability", "description": "nice", "line": "", "current_code": "pass", "suggested_fix": ""},
        ]
        result, _skip_reasons = ReviewItemFactory().create(item_dicts, str(tmp_path))
        assert len(result) == 1
        assert result[0].file_path == "src/lib.py"

    def test_empty_file_path_passes_validation(self, tmp_path: Path) -> None:
        """Items with empty file_path are not validated (cross-cutting findings)."""
        item_dicts: list[dict[str, Any]] = [
            {"file": "", "severity": "major", "category": "architecture", "description": "global concern", "line": "", "current_code": "", "suggested_fix": ""},
        ]
        result, _skip_reasons = ReviewItemFactory().create(item_dicts, str(tmp_path))
        assert len(result) == 1

    def test_item_with_description_kept_even_without_code_evidence(
        self, tmp_path: Path
    ) -> None:
        """Items with a description are kept even without current_code/suggested_fix."""
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
        result, _skip_reasons = ReviewItemFactory().create(item_dicts, str(tmp_path))
        assert len(result) == 2
        assert result[0].description == "hallucinated finding"
        assert result[1].description == "cross-cutting is fine"

    def test_empty_repo_path_disables_validation(self, tmp_path: Path) -> None:
        """Empty repo_path disables path validation."""
        item_dicts: list[dict[str, Any]] = [
            {"file": "src/foo.py", "severity": "major", "category": "bug", "description": "bad", "line": "1", "current_code": "pass", "suggested_fix": "return None"},
            {"file": "src/nonexistent.py", "severity": "critical", "category": "security", "description": "fake", "line": "", "current_code": "", "suggested_fix": ""},
        ]
        result, _skip_reasons = ReviewItemFactory().create(item_dicts, "")
        assert len(result) == 2

    def test_keeps_crosscutting_findings_without_file_path(
        self, tmp_path: Path
    ) -> None:
        """Cross-cutting findings (no file path) are preserved."""
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
        result, _skip_reasons = ReviewItemFactory().create(item_dicts, str(tmp_path))
        assert len(result) == 1
        assert result[0].description == "No error handling for file not found cases across the codebase"

    def test_drops_items_with_invalid_line_numbers(self, tmp_path: Path) -> None:
        """Items with invalid line numbers are dropped."""
        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "src" / "foo.py").write_text("\n".join(["line " + str(i) for i in range(1, 11)]))
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
        result, _skip_reasons = ReviewItemFactory().create(item_dicts, str(tmp_path))
        assert len(result) == 1
        assert result[0].description == "valid line"

    def test_drops_items_with_mismatched_code(self, tmp_path: Path) -> None:
        """Items whose current_code doesn't match file content are dropped."""
        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "src" / "foo.py").write_text("def foo():\n    return 42")
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
        result, _skip_reasons = ReviewItemFactory().create(item_dicts, str(tmp_path))
        assert len(result) == 1
        assert result[0].description == "correct code"

    def test_fabricated_error_description_skipped(self, tmp_path: Path) -> None:
        """Findings with error-pattern description and no code evidence are dropped.

        This covers the novel path where suggested_fix is non-empty prose
        (bypassing the empty-code-evidence check) but current_code is empty
        AND the description matches fabricated-error patterns.
        """
        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "src" / "real.py").write_text("def foo(): pass")
        item_dicts: list[dict[str, Any]] = [
            {
                "file": "src/real.py",
                "severity": "info",
                "category": "quality",
                "description": "File not found in repository path — unable to verify this module",
                "line": "",
                "current_code": "",
                "suggested_fix": "Confirm the file exists and re-run the review",
            },
        ]
        items, _reasons = ReviewItemFactory().create(item_dicts, str(tmp_path))
        assert len(items) == 0

    def test_error_description_with_code_evidence_not_skipped(
        self, tmp_path: Path
    ) -> None:
        """Legitimate findings mentioning error patterns WITH code are kept."""
        (tmp_path / "src").mkdir(parents=True)
        (tmp_path / "src" / "handler.py").write_text("try: ...\nexcept: pass")
        item_dicts: list[dict[str, Any]] = [
            {
                "file": "src/handler.py",
                "severity": "major",
                "category": "error_handling",
                "description": "Bare except clause — file not found errors are silently swallowed",
                "line": "2",
                "current_code": "except: pass",
                "suggested_fix": "except FileNotFoundError as e: logger.error(e)",
            },
        ]
        items, _reasons = ReviewItemFactory().create(item_dicts, str(tmp_path))
        assert len(items) == 1
        assert items[0].description == "Bare except clause — file not found errors are silently swallowed"

    def test_fabricated_error_cross_cutting_not_affected(
        self, tmp_path: Path
    ) -> None:
        """Cross-cutting findings with error descriptions are kept (no file_path)."""
        item_dicts: list[dict[str, Any]] = [
            {
                "file": "",
                "severity": "major",
                "category": "architecture",
                "description": "No error handling for file not found cases across the codebase",
                "line": "",
                "current_code": "",
                "suggested_fix": "Add centralized file-not-found error handling middleware",
            },
        ]
        items, _reasons = ReviewItemFactory().create(item_dicts, str(tmp_path))
        assert len(items) == 1
        assert items[0].description == "No error handling for file not found cases across the codebase"
