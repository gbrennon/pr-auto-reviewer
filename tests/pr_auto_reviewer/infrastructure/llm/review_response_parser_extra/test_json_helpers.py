from ._helpers import *


class TestJsonHelpers:
    """Exercises JSON discovery and sanitization helpers."""

    def test_extract_outermost_json_when_balanced_then_extracts(self) -> None:
        text = 'preamble {"a": {"b": 1}} trailing'

        assert ReviewResponseParser.extract_outermost_json(text) == '{"a": {"b": 1}}'

    def test_extract_outermost_json_when_no_braces_then_none(self) -> None:
        assert ReviewResponseParser.extract_outermost_json("plain text") is None

    def test_extract_outermost_json_when_unclosed_then_none(self) -> None:
        assert ReviewResponseParser.extract_outermost_json('{"a": 1') is None

    def test_sanitize_json_literals_when_control_chars_then_escaped(self) -> None:
        raw = '{"desc": "line1\nline2\ttab"}'

        cleaned = ReviewResponseParser.sanitize_json_literals(raw)

        assert "\\n" in cleaned
        assert "\\t" in cleaned
        assert json_loads(cleaned)["desc"] == "line1\nline2\ttab"

    def test_sanitize_json_literals_when_escapes_preserved(self) -> None:
        raw = '{"desc": "already \\"quoted\\""}'

        assert ReviewResponseParser.sanitize_json_literals(raw) == raw

    def test_normalize_item_dict_when_high_severity_then_major(self) -> None:
        item = ReviewResponseParser.normalize_item_dict(
            {"file": "a.py", "severity": "high", "category": "bug", "description": "d"}
        )

        assert item["severity"] == "major"
        assert item["category"] == "bug"

    def test_normalize_item_dict_when_type_key_then_category(self) -> None:
        item = ReviewResponseParser.normalize_item_dict(
            {"file": "a.py", "type": "security", "description": "d"}
        )

        assert item["category"] == "security"

    def test_normalize_item_dict_when_unknown_category_then_default(self) -> None:
        item = ReviewResponseParser.normalize_item_dict(
            {"file": "a.py", "category": "weird", "description": "d"}
        )

        assert item["category"] == "maintainability"

    def test_normalize_item_dict_when_no_fix_then_synthesized(self) -> None:
        item = ReviewResponseParser.normalize_item_dict(
            {"file": "a.py", "description": "found a bug"}
        )

        assert "found a bug" in item["suggested_fix"]

    def test_normalize_item_dict_when_issue_title_message_then_description(self) -> None:
        item = ReviewResponseParser.normalize_item_dict(
            {"issue": "issue text", "title": "title text", "message": "msg"}
        )

        assert item["description"] == "issue text"

    def test_normalize_item_dict_when_code_aliases_then_mapped(self) -> None:
        item = ReviewResponseParser.normalize_item_dict(
            {"file_path": "b.py", "code": "x", "fix": "y", "description": "d"}
        )

        assert item["file"] == "b.py"
        assert item["current_code"] == "x"
        assert item["suggested_fix"] == "y"

    def test_is_concrete_when_both_then_true(self) -> None:
        assert ReviewResponseParser._is_concrete({"current_code": "x", "suggested_fix": "y"}) is True

    def test_is_concrete_when_missing_fix_then_false(self) -> None:
        assert ReviewResponseParser._is_concrete({"current_code": "x"}) is False

    def test_find_items_when_direct_then_found(self) -> None:
        data = {"items": [{"file": "a.py"}, "skip-me"]}

        result = ReviewResponseParser()._find_items_in_dict(data)

        assert result == [{"file": "a.py"}]

    def test_find_items_when_nested_dict_then_found(self) -> None:
        data = {"top": {"deep": {"findings": [{"file": "a.py"}]}}}

        assert ReviewResponseParser()._find_items_in_dict(data) == [{"file": "a.py"}]

    def test_find_items_when_nested_list_then_found(self) -> None:
        data = {"top": [{"issues": [{"file": "a.py"}]}]}

        assert ReviewResponseParser()._find_items_in_dict(data) == [{"file": "a.py"}]

    def test_find_items_when_none_then_empty(self) -> None:
        assert ReviewResponseParser()._find_items_in_dict({"top": "x"}) == []

