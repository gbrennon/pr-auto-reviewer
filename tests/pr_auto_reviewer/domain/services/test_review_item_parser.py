"""Tests for ReviewItemParser domain service."""

from pr_auto_reviewer.domain import ItemSeverity, ReviewItem
from pr_auto_reviewer.domain.services import ReviewItemParser


class TestReviewItemParser:
    """Tests for ReviewItemParser.parse(raw_body) -> list[ReviewItem]."""

    def test_empty_body_returns_empty_list(self) -> None:
        parser = ReviewItemParser()
        result = parser.parse("")
        assert result == []

    def test_body_with_no_matches_returns_empty_list(self) -> None:
        parser = ReviewItemParser()
        result = parser.parse("Just a regular comment\nNo review items here.")
        assert result == []

    def test_body_with_no_numbered_items_returns_empty_list(self) -> None:
        parser = ReviewItemParser()
        result = parser.parse("**CRITICAL** [security] `src/main.py`: issue")
        assert result == []

    def test_unknown_severity_defaults_to_info(self) -> None:
        parser = ReviewItemParser()
        raw = "1. [general] [UNKNOWN]\n\nSomething minor"
        result = parser.parse(raw)
        assert len(result) == 1
        assert result[0].severity == ItemSeverity.INFO
        assert result[0].id  # ID is generated
        assert result[0].category == "general"
        assert result[0].file_path is None
        assert result[0].description == "Something minor"

    def test_parse_critical_with_file(self) -> None:
        parser = ReviewItemParser()
        raw = "1. [security] [CRITICAL] src/main.py:42\n\nSQL injection risk"
        result = parser.parse(raw)
        assert len(result) == 1
        item = result[0]
        assert item.id  # ID is generated
        assert item.severity == ItemSeverity.CRITICAL
        assert item.category == "security"
        assert item.file_path == "src/main.py"
        assert item.line == "42"
        assert item.description == "SQL injection risk"

    def test_parse_major_without_file(self) -> None:
        parser = ReviewItemParser()
        raw = "2. [style] [MAJOR]\n\nConsider adding type hints"
        result = parser.parse(raw)
        assert len(result) == 1
        item = result[0]
        assert item.id  # ID is generated
        assert item.severity == ItemSeverity.MAJOR
        assert item.category == "style"
        assert item.file_path is None
        assert item.description == "Consider adding type hints"

    def test_parse_minor(self) -> None:
        parser = ReviewItemParser()
        raw = "3. [docs] [MINOR] README.md:10\n\nFix typo in usage section"
        result = parser.parse(raw)
        assert len(result) == 1
        item = result[0]
        assert item.id  # ID is generated
        assert item.severity == ItemSeverity.MINOR
        assert item.category == "docs"
        assert item.file_path == "README.md"
        assert item.line == "10"
        assert item.description == "Fix typo in usage section"

    def test_parse_info(self) -> None:
        parser = ReviewItemParser()
        raw = "4. [naming] [INFO]\n\nVariable x should be renamed"
        result = parser.parse(raw)
        assert len(result) == 1
        item = result[0]
        assert item.id  # ID is generated
        assert item.severity == ItemSeverity.INFO
        assert item.category == "naming"
        assert item.file_path is None
        assert item.description == "Variable x should be renamed"

    def test_parse_multiple_items_sequential_numbering(self) -> None:
        parser = ReviewItemParser()
        raw = (
            "1. [security] [CRITICAL] src/main.py:42\n\nSQL injection risk\n"
            "2. [style] [MAJOR]\n\nConsider adding type hints\n"
            "3. [docs] [MINOR] README.md:10\n\nFix typo"
        )
        result = parser.parse(raw)
        assert len(result) == 3
        assert result[0].id  # ID is generated
        assert result[0].severity == ItemSeverity.CRITICAL
        assert result[0].category == "security"
        assert result[0].file_path == "src/main.py"
        assert result[0].description == "SQL injection risk"
        assert result[1].id  # ID is generated
        assert result[1].severity == ItemSeverity.MAJOR
        assert result[1].category == "style"
        assert result[1].file_path is None
        assert result[1].description == "Consider adding type hints"
        assert result[2].id  # ID is generated
        assert result[2].severity == ItemSeverity.MINOR
        assert result[2].category == "docs"
        assert result[2].file_path == "README.md"
        assert result[2].description == "Fix typo"

    def test_parse_non_sequential_numbers(self) -> None:
        parser = ReviewItemParser()
        raw = (
            "5. [security] [CRITICAL] src/main.py:42\n\nSQL injection risk\n"
            "6. [style] [MAJOR]\n\nConsider adding type hints"
        )
        result = parser.parse(raw)
        assert len(result) == 2
        assert result[0].id  # ID is generated
        assert result[1].id  # ID is generated

    def test_parse_mixed_severity_cases(self) -> None:
        """The regex requires uppercase severity; lowercase won't match."""
        parser = ReviewItemParser()
        raw = "1. [security] [critical]\n\nSQL injection risk"
        result = parser.parse(raw)
        assert result == []

    def test_parse_compact_format_description_on_same_line(self) -> None:
        parser = ReviewItemParser()
        raw = "1. [bug] [MAJOR] This is a bug description"
        result = parser.parse(raw)
        assert len(result) == 1
        item = result[0]
        assert item.id  # ID is generated
        assert item.severity == ItemSeverity.MAJOR
        assert item.category == "bug"
        assert item.file_path is None
        assert item.description == "This is a bug description"

    def test_parse_file_path_with_line_no_and_no_description(self) -> None:
        """file_info 'src/main.py:42' with no description → file+line, empty desc."""
        parser = ReviewItemParser()
        raw = "1. [security] [CRITICAL] src/main.py:42"
        result = parser.parse(raw)
        assert len(result) == 1
        item = result[0]
        assert item.file_path == "src/main.py"
        assert item.line == "42"
        assert item.description == ""

    def test_parse_header_only_with_no_file_and_no_description(self) -> None:
        """A bare numbered header yields no file_path, no line, empty desc."""
        parser = ReviewItemParser()
        raw = "1. [general] [INFO]"
        result = parser.parse(raw)
        assert len(result) == 1
        item = result[0]
        assert item.file_path is None
        assert item.line == ""
        assert item.description == ""

    def test_parse_with_no_separator(self) -> None:
        parser = ReviewItemParser()
        raw = "1. [general] [INFO]\n\nJust a note"
        result = parser.parse(raw)
        assert len(result) == 1
        item = result[0]
        assert item.severity == ItemSeverity.INFO
        assert item.category == "general"
        assert item.file_path is None
        assert item.description == "Just a note"

    def test_parse_skips_non_matching_lines(self) -> None:
        parser = ReviewItemParser()
        raw = (
            "Here is my review:\n"
            "1. [security] [CRITICAL] src/main.py:42\n\nSQL injection risk\n"
            "Some extra text in between\n"
            "2. [style] [MAJOR]\n\nConsider adding type hints"
        )
        result = parser.parse(raw)
        assert len(result) == 2
        assert result[0].id  # ID is generated
        assert result[1].id  # ID is generated

    def test_return_type_is_list_of_review_items(self) -> None:
        parser = ReviewItemParser()
        raw = "1. [security] [CRITICAL] src/main.py:42\n\nSQL injection risk"
        result = parser.parse(raw)
        assert isinstance(result, list)
        assert all(isinstance(ri, ReviewItem) for ri in result)

    def test_parse_full_review_body(self) -> None:
        parser = ReviewItemParser()
        raw = (
            "## AI Code Review\n\n"
            "**Verdict:** Approved\n\n"
            "### Issues\n\n"
            "0. [maintainability] [MINOR]\n\n"
            "Confirm implementations for all ports\n"
            "1. [maintainability] [MINOR]\n\n"
            "Clarify the role of application\n"
            "2. [security] [CRITICAL] src/auth.py:10\n\n"
            "SQL injection risk\n"
            "3. [style] [MAJOR] README.md:5\n\nFix typo\n"
            "### Praise\n\n"
            "No notable patterns\n"
        )
        result = parser.parse(raw)
        assert len(result) == 4
        assert result[0].id  # ID is generated
        assert result[0].description == "Confirm implementations for all ports"
        assert result[2].id  # ID is generated
        assert result[2].severity == ItemSeverity.CRITICAL
        assert result[2].file_path == "src/auth.py"
        assert result[2].line == "10"
