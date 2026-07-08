"""Tests for IssueCommandParser domain service."""

import pytest

from pr_auto_reviewer.domain import IssueCommand
from pr_auto_reviewer.domain.services import IssueCommandParser

class TestIssueCommandParser:
    """Tests for IssueCommandParser.parse(comment_id, comment_body) -> IssueCommand | None."""

    def test_parse_create_issue_with_multiple_numbers(self) -> None:
        parser = IssueCommandParser()
        result = parser.parse("c_12345", "/create-issue 1,2,3")
        assert result is not None
        assert isinstance(result, IssueCommand)
        assert result.comment_id == "c_12345"
        assert result.item_numbers == [1, 2, 3]

    def test_parse_create_issue_with_single_number(self) -> None:
        parser = IssueCommandParser()
        result = parser.parse("c_abc", "/create-issue 5")
        assert result is not None
        assert result.comment_id == "c_abc"
        assert result.item_numbers == [5]

    def test_parse_regular_comment_returns_none(self) -> None:
        parser = IssueCommandParser()
        result = parser.parse("c_12345", "regular comment")
        assert result is None

    def test_parse_no_create_issue_prefix_returns_none(self) -> None:
        parser = IssueCommandParser()
        result = parser.parse("c_12345", "/other-command 1,2,3")
        assert result is None

    def test_parse_create_issue_with_no_digits_returns_none(self) -> None:
        parser = IssueCommandParser()
        result = parser.parse("c_12345", "/create-issue abc")
        assert result is None

    def test_parse_create_issue_with_empty_numbers_returns_none(self) -> None:
        parser = IssueCommandParser()
        result = parser.parse("c_12345", "/create-issue ,")
        assert result is None

    def test_parse_create_issue_case_insensitive(self) -> None:
        parser = IssueCommandParser()
        result = parser.parse("c_xyz", "/CREATE-ISSUE 7,8")
        assert result is not None
        assert result.item_numbers == [7, 8]

    def test_parse_create_issue_mixed_case_command(self) -> None:
        parser = IssueCommandParser()
        result = parser.parse("c_xyz", "/Create-Issue 3,4")
        assert result is not None
        assert result.item_numbers == [3, 4]

    def test_parse_create_issue_with_spaces(self) -> None:
        parser = IssueCommandParser()
        result = parser.parse("c_12345", "/create-issue   1 , 2 , 3")
        assert result is not None
        assert result.item_numbers == [1, 2, 3]

    def test_parse_create_issue_ignores_non_numeric_parts(self) -> None:
        parser = IssueCommandParser()
        result = parser.parse("c_12345", "/create-issue 1,abc,3")
        assert result is not None
        assert result.item_numbers == [1]

    def test_parse_create_issue_embedded_in_longer_text(self) -> None:
        parser = IssueCommandParser()
        result = parser.parse(
            "c_12345",
            "Please create issues for the review items.\n/create-issue 1,2,3\nThanks!"
        )
        assert result is not None
        assert result.item_numbers == [1, 2, 3]

    def test_parse_empty_string_returns_none(self) -> None:
        parser = IssueCommandParser()
        result = parser.parse("c_12345", "")
        assert result is None

    def test_parse_only_whitespace_returns_none(self) -> None:
        parser = IssueCommandParser()
        result = parser.parse("c_12345", "   \n  \t  ")
        assert result is None

    def test_result_is_frozen_dataclass(self) -> None:
        parser = IssueCommandParser()
        result = parser.parse("c_12345", "/create-issue 1,2")
        assert result is not None
        with pytest.raises(Exception):
            result.item_numbers = [3]
