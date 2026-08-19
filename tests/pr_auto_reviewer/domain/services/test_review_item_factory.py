"""Tests for ReviewItemFactory domain service."""

from __future__ import annotations

import pytest
from pathlib import Path
import os
import shutil
from unittest.mock import patch

from pr_auto_reviewer.domain.services.review_item_factory import ReviewItemFactory
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict


class TestReviewItemFactory:
    """Tests for ReviewItemFactory domain service."""

    def test_extract_backticked_symbols(self) -> None:
        """Test extracting backticked symbol names."""
        result = ReviewItemFactory._extract_symbols(
            "Refer to `get_user` function"
        )
        assert "get_user" in result

    def test_extract_candidate_symbols(self) -> None:
        """Test extracting candidate symbols from description."""
        result = ReviewItemFactory._extract_symbols(
            "function process_data() failed"
        )
        assert len(result) > 0

    def test_filter_symbols_min_length(self) -> None:
        """Test that symbols shorter than 2 chars are filtered out."""
        result = ReviewItemFactory._extract_symbols("a b c")
        assert all(len(s) > 1 for s in result)

    def test_generate_id_format(self) -> None:
        """Test generated ID format."""
        result = ReviewItemFactory._generate_id()
        assert len(result) == 6
        int(result, 16)

        # Method no longer accepts repo/pr params - always returns short format
        result_without_params = ReviewItemFactory._generate_id()
        assert len(result_without_params) == 6
        int(result_without_params, 16)

    def test_resolve_exact_path(self) -> None:
        """Test resolving an exact repo-relative path."""
        with Path("/tmp/test_resolve.py").open("w") as f:
            f.write("x = 1\n")

        try:
            result_path, result_str = ReviewItemFactory._resolve_file_path(
                "test_resolve.py", Path("/tmp"), ["test_resolve.py"]
            )
            assert result_path is not None
            assert result_str == "test_resolve.py"
        finally:
            Path("/tmp/test_resolve.py").unlink(missing_ok=True)

    def test_resolve_partial_path(self) -> None:
        """Test resolving a partial path against changed files."""
        os.makedirs("/tmp/pkg", exist_ok=True)
        with Path("/tmp/pkg/module.py").open("w") as f:
            f.write("y = 2\n")

        with Path("/tmp/main.py").open("w") as f:
            f.write("z = 3\n")

        try:
            result_path, result_str = ReviewItemFactory._resolve_file_path(
                "module.py", Path("/tmp"), ["module.py"]
            )
            assert result_str == "module.py"
        finally:
            Path("/tmp/pkg/module.py").unlink(missing_ok=True)
            Path("/tmp/main.py").unlink(missing_ok=True)
            os.rmdir("/tmp/pkg")

    def test_unresolvable_path(self) -> None:
        """Test that unresolvable paths return None."""
        result_path, result_str = ReviewItemFactory._resolve_file_path(
            "nonexistent.py", Path("/tmp"), ["other.py"]
        )
        assert result_path is None

    def test_create_with_valid_items(self) -> None:
        """Test creating ReviewItems from valid dicts."""
        item_dicts = [
            {
                "file": "src/main.py",
                "description": "Test finding",
                "severity": "minor",
                "category": "bug",
                "current_code": "x = 1",
                "suggested_fix": "x = 2",
            }
        ]

        repo_path = "/tmp/test_repo"
        changed_files = ["src/main.py"]

        repo = Path(repo_path)
        repo.mkdir(parents=True, exist_ok=True)
        (repo / "src/main.py").parent.mkdir(parents=True, exist_ok=True)
        (repo / "src/main.py").write_text("x = 1\n")

        try:
            items, skip_reasons = ReviewItemFactory.create(
                item_dicts, repo_path, changed_files
            )
            assert len(items) == 1
            assert len(skip_reasons) == 0
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)

    def test_create_skips_non_dict(self) -> None:
        """Test that non-dict items are skipped with warning."""
        item_dicts = ["not a dict", 123, None]

        with patch("pr_auto_reviewer.domain.services.review_item_factory.logger.warning") as mock_warn:
            items, skip_reasons = ReviewItemFactory.create(
                item_dicts, "/tmp", None
            )
            assert len(items) == 0
            assert mock_warn.call_count >= 1

    def test_create_skips_empty_description(self) -> None:
        """Test that items without description are skipped when file_path exists."""
        item_dicts = [
            {
                "file": "src/main.py",
                "description": "",
                "severity": "minor",
                "category": "bug",
            }
        ]

        repo_path = "/tmp/test_repo2"
        repo = Path(repo_path)
        repo.mkdir(parents=True, exist_ok=True)
        (repo / "src/main.py").parent.mkdir(parents=True, exist_ok=True)
        (repo / "src/main.py").write_text("x = 1\n")

        try:
            items, skip_reasons = ReviewItemFactory.create(
                item_dicts, repo_path, ["src/main.py"]
            )
            assert len(skip_reasons) > 0
            assert len(items) == 0
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)

    def test_create_fabricated_narrative(self) -> None:
        """Test that fabricated error patterns are detected."""
        item_dicts = [
            {
                "file": "src/main.py",
                "description": "file not found: cannot access the module",
                "severity": "minor",
                "category": "bug",
            }
        ]

        repo_path = "/tmp/test_repo3"
        repo = Path(repo_path)
        repo.mkdir(parents=True, exist_ok=True)
        (repo / "src/main.py").parent.mkdir(parents=True, exist_ok=True)
        (repo / "src/main.py").write_text("x = 1\n")

        try:
            items, skip_reasons = ReviewItemFactory.create(
                item_dicts, repo_path, ["src/main.py"]
            )
            assert len(skip_reasons) > 0
            assert len(items) == 0
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)

    def test_create_with_missing_file(self) -> None:
        """Test that items with missing files are skipped."""
        item_dicts = [
            {
                "file": "src/nonexistent.py",
                "description": "Test finding",
                "severity": "minor",
                "category": "bug",
            }
        ]

        repo_path = "/tmp/test_repo4"
        repo = Path(repo_path)
        repo.mkdir(parents=True, exist_ok=True)

        try:
            items, skip_reasons = ReviewItemFactory.create(
                item_dicts, repo_path, ["src/main.py"]
            )
            assert len(skip_reasons) > 0
            assert len(items) == 0
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)

    def test_create_generates_ids(self) -> None:
        """Test that each item gets a unique ID."""
        with patch.object(ReviewItemFactory, "_generate_id", side_effect=[__import__("uuid").uuid7(), __import__("uuid").uuid7()]):
            item_dicts = [
                {
                    "file": "src/main.py",
                    "description": "Finding 1",
                    "severity": "minor",
                    "category": "bug",
                },
                {
                    "file": "src/main.py",
                    "description": "Finding 2",
                    "severity": "major",
                    "category": "quality",
                },
            ]

            repo_path = "/tmp/test_repo5"
            repo = Path(repo_path)
            repo.mkdir(parents=True, exist_ok=True)
            (repo / "src/main.py").parent.mkdir(parents=True, exist_ok=True)
            (repo / "src/main.py").write_text("x = 1\n")

            try:
                items, skip_reasons = ReviewItemFactory.create(
                    item_dicts, repo_path, ["src/main.py"]
                )
                assert len(items) == 2
                item_ids = [item.id for item in items]
                assert len(set(item_ids)) == 2, f"Expected 2 unique IDs, got {item_ids}"
            finally:
                import shutil
                shutil.rmtree(repo_path, ignore_errors=True)

    def test_create_preserves_fields(self) -> None:
        """Test that file_path, description, severity, category are preserved."""
        item_dicts = [
            {
                "file": "src/client.py",
                "description": "Logger at info level",
                "severity": "minor",
                "category": "maintainability",
                "current_code": "logger.info('test')",
                "suggested_fix": "logger.debug('test')",
            }
        ]

        repo_path = "/tmp/test_repo6"
        repo = Path(repo_path)
        repo.mkdir(parents=True, exist_ok=True)
        (repo / "src/client.py").parent.mkdir(parents=True, exist_ok=True)
        (repo / "src/client.py").write_text("logger.info('test')\n")

        try:
            items, skip_reasons = ReviewItemFactory.create(
                item_dicts, repo_path, ["src/client.py"]
            )
            assert len(items) == 1
            item = items[0]
            assert item.file_path == "src/client.py"
            assert item.description == "Logger at info level"
            assert item.severity == ItemSeverity.MINOR
            assert item.category == IssueCategory.MAINTAINABILITY
            assert item.line == "1-1"
            assert item.current_code == "logger.info('test')"
            assert item.suggested_fix == "logger.debug('test')"
        finally:
            shutil.rmtree(repo_path, ignore_errors=True)


class TestEnsureUniqueIds:
    """Tests for ReviewItemFactory.ensure_unique_ids."""

    def _item(self, id: str) -> ReviewItem:
        return ReviewItem(
            severity=ItemSeverity.INFO,
            category=IssueCategory.GENERAL,
            file_path=None,
            description="",
            id=id,
        )

    def test_duplicate_and_empty_ids_become_globally_unique(self) -> None:
        """Items, suggestions, and praise share one id space with no collisions."""
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            items=[self._item("a1"), self._item("a1"), self._item("")],
            suggestions=[self._item("a1"), self._item("b2")],
            praise=[self._item("")],
        )

        result = ReviewItemFactory.ensure_unique_ids(review)

        all_items = result.items + result.suggestions + result.praise
        assert all(item.id for item in all_items)
        assert len({item.id for item in all_items}) == len(all_items)

    def test_preserves_existing_unique_id(self) -> None:
        """A unique, truthy id is left untouched."""
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            items=[self._item("b2")],
        )

        result = ReviewItemFactory.ensure_unique_ids(review)

        assert result.items[0].id == "b2"