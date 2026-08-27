from ._helpers import *


class TestParseStreamingResponse:
    """Exercises the shared stream parser."""

    def test_parse_when_items_list_then_maps_items(self) -> None:
        items, metadata = _client().parse_streaming_response(
            ['{"verdict": "approved", "items": [{"file": "a.py", "severity": "major", "category": "bug", "description": "d", "line": 3, "current_code": "x", "suggested_fix": "y"}]}'],
            "code-review:latest",
        )

        assert items is not None
        assert items[0]["file"] == "a.py"
        assert items[0]["severity"] == "major"
        assert items[0]["category"] == "bug"
        assert metadata["verdict"] == "approved"

    def test_parse_when_findings_key_then_maps_items(self) -> None:
        items, _ = _client().parse_streaming_response(
            ['{"findings": [{"file": "b.py", "severity": "minor"}]}'],
            "m",
        )

        assert items is not None
        assert items[0]["file"] == "b.py"

    def test_parse_when_issues_key_then_maps_items(self) -> None:
        items, _ = _client().parse_streaming_response(
            ['{"issues": [{"file": "c.py", "severity": "info"}]}'],
            "m",
        )

        assert items is not None
        assert items[0]["file"] == "c.py"

    def test_parse_when_items_not_a_list_then_items_none(self) -> None:
        items, _ = _client().parse_streaming_response(
            ['{"items": {"file": "a.py"}}'],
            "m",
        )

        assert items is None

    def test_parse_when_items_has_non_dict_then_filters(self) -> None:
        items, _ = _client().parse_streaming_response(
            ['{"items": ["plain", {"file": "a.py", "severity": "minor"}]}'],
            "m",
        )

        assert items is not None
        assert len(items) == 1

    def test_parse_when_item_missing_keys_then_defaults(self) -> None:
        items, _ = _client().parse_streaming_response(
            ['{"items": [{}]}'],
            "m",
        )

        assert items is not None
        assert items[0]["file"] == ""
        assert items[0]["severity"] == "info"
        assert items[0]["category"] == "maintainability"

    def test_parse_when_invalid_json_then_decode_fallback(self) -> None:
        items, metadata = _client().parse_streaming_response(["not json"], "m")

        assert items is None
        assert metadata["verdict"] == "commented"
        assert "failed to decode" in metadata["reason"]

    def test_parse_when_missing_keys_then_metadata_defaults(self) -> None:
        _, metadata = _client().parse_streaming_response(['{"verdict": "commented"}'], "m")

        assert metadata["reason"] == ""
        assert metadata["summary"] == ""
        assert metadata["suggestions"] == []
        assert metadata["praise"] == []

