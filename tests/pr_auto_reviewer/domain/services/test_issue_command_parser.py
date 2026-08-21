"""Tests for IssueCommandParser domain service."""

from __future__ import annotations

import pytest

from pr_auto_reviewer.domain.services.issue_command_parser import IssueCommandParser
from pr_auto_reviewer.domain.value_objects.issue_command import IssueCommand


class TestIssueCommandParser:
    """Tests for IssueCommandParser - pure domain service."""

    def test_parse_valid_command(self) -> None:
        """Test parsing a valid /create issue command."""
        parser = IssueCommandParser()
        result = parser.parse("test/comment-id", "/create issue a3f2,b7d1")

        assert result is not None
        assert result.comment_id == "test/comment-id"
        assert result.item_ids == ["a3f2", "b7d1"]

    def test_parse_command_with_prefix(self) -> None:
        """Test parsing with /create issue for prefix."""
        parser = IssueCommandParser()
        result = parser.parse("test/id", "/create issue for c4e5")

        assert result is not None
        assert result.comment_id == "test/id"
        assert result.item_ids == ["c4e5"]

    def test_parse_command_mixed_case(self) -> None:
        """Test parsing preserves case of IDs."""
        parser = IssueCommandParser()
        result = parser.parse("test", "/CREATE ISSUE X1,Y2")

        assert result is not None
        # IDs are captured as-is (case preserved)
        assert result.item_ids == ["X1", "Y2"]

    def test_parse_no_command_returns_none(self) -> None:
        """Test that non-matching bodies return None."""
        parser = IssueCommandParser()
        assert parser.parse("id", "just some regular comment text") is None
        assert parser.parse("id", "") is None
        assert parser.parse("id", "/create issue") is None

    def test_parse_empty_ids_returns_none(self) -> None:
        """Test that empty IDs after the command return None."""
        parser = IssueCommandParser()
        assert parser.parse("id", "/create issue   ") is None

    def test_parse_command_with_no_ids(self) -> None:
        """Test that command with no IDs returns None (hits line 33)."""
        parser = IssueCommandParser()
        # Pattern matches "create issue" but no IDs follow, so ids list is empty
        assert parser.parse("id", "/create issue") is None

    def test_parse_single_id(self) -> None:
        """Test parsing a single item ID."""
        parser = IssueCommandParser()
        result = parser.parse("id", "/create issue xyz123")

        assert result is not None
        assert result.item_ids == ["xyz123"]

    def test_issue_command_creation(self) -> None:
        """Test IssueCommand VO creation."""
        cmd = IssueCommand(comment_id="test-id", item_ids=["a1", "b2"])

        assert cmd.comment_id == "test-id"
        assert cmd.item_ids == ["a1", "b2"]