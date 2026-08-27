from ._helpers import *


class TestItemDictExtraction:
    """Exercises item-dict extraction and the parse_items pipeline."""

    def test_extract_item_dicts_when_json_block_then_normalized(self) -> None:
        raw = '```json\n{"items": [{"file": "a.py", "severity": "high", "description": "d"}]}\n```'

        result = ReviewResponseParser()._extract_item_dicts(raw)

        assert result[0]["severity"] == "major"

    def test_extract_item_dicts_when_nested_then_found(self) -> None:
        raw = '{"top": {"issues": [{"file": "a.py", "description": "d"}]}}'

        result = ReviewResponseParser()._extract_item_dicts(raw)

        assert result[0]["file"] == "a.py"

    def test_extract_item_dicts_when_list_then_normalized(self) -> None:
        raw = '[{"file": "a.py", "severity": "low", "description": "d"}]'

        result = ReviewResponseParser()._extract_item_dicts(raw)

        assert result[0]["severity"] == "minor"

    def test_extract_item_dicts_when_invalid_then_empty(self) -> None:
        assert ReviewResponseParser()._extract_item_dicts("not json at all") == []

    def test_parse_items_when_json_list_then_concrete(self) -> None:
        raw = '[{"file": "a.py", "severity": "major", "description": "d", "current_code": "x", "suggested_fix": "y"}]'

        result = ReviewResponseParser().parse_items(raw)

        assert result[0]["file"] == "a.py"

    def test_parse_items_when_nested_dict_then_concrete(self) -> None:
        raw = '{"analysis": {"findings": [{"file": "a.py", "description": "d", "current_code": "x", "suggested_fix": "y"}]}}'

        result = ReviewResponseParser().parse_items(raw)

        assert result[0]["file"] == "a.py"

    def test_parse_items_when_outermost_json_then_concrete(self) -> None:
        raw = 'preamble text {"items": [{"file": "a.py", "description": "d", "current_code": "x", "suggested_fix": "y"}]} tail'

        result = ReviewResponseParser().parse_items(raw)

        assert result[0]["file"] == "a.py"

    def test_parse_items_when_markdown_bullets_then_items(self) -> None:
        raw = "- [major] bug (src/a.py) Unused import"

        result = ReviewResponseParser().parse_items(raw)

        assert result[0]["file"] == "src/a.py"

    def test_parse_items_when_prose_section_then_items(self) -> None:
        result = ReviewResponseParser().parse_items(_prose_issues_content())

        assert len(result) == 2

    def test_parse_items_when_unparsable_then_empty(self) -> None:
        assert ReviewResponseParser().parse_items("*?* unparseable garbage") == []

    def test_parse_item_observations_when_fixless_then_observations(self) -> None:
        raw = '{"items": [{"file": "a.py", "current_code": "x"}]}'

        result = ReviewResponseParser().parse_item_observations(raw)

        assert result == [{"file": "a.py", "line": "", "description": "Review the identified concern."}]

    def test_parse_item_observations_when_concrete_then_skipped(self) -> None:
        raw = '{"items": [{"file": "a.py", "description": "d", "current_code": "x", "suggested_fix": "y"}]}'

        assert ReviewResponseParser().parse_item_observations(raw) == []

