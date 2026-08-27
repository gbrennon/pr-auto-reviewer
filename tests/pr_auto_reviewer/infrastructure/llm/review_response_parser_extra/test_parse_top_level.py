from ._helpers import *


class TestParseTopLevel:
    """Exercises the public parse() entry point end to end."""

    def test_parse_when_json_with_stop_token_then_parsed(self) -> None:
        raw = '{"verdict": "approved", "reason": "r", "summary": "s"}<|im_end|>'

        result = ReviewResponseParser().parse(raw, "m")

        assert result.verdict == ReviewVerdict.APPROVED

    def test_parse_when_json_in_code_block_then_parsed(self) -> None:
        raw = '```json\n{"verdict": "changes_requested", "summary": "ok"}\n```'

        result = ReviewResponseParser().parse(raw, "m")

        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED

    def test_parse_when_embedded_json_then_extracted(self) -> None:
        raw = 'note {"verdict": "approved", "summary": "fine"} note'

        result = ReviewResponseParser().parse(raw, "m")

        assert result.verdict == ReviewVerdict.APPROVED

    def test_parse_when_json_items_infer_fields(self) -> None:
        raw = (
            '{"verdict": "changes_requested", "items": ['
            '{"file": "a.py", "description": {"issue": "unused var"}, "severity": "high"}]}'
        )

        result = ReviewResponseParser().parse(raw, "m")

        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert result.items[0].file_path == "a.py"
        assert "issue=unused var" in result.items[0].description

    def test_parse_when_json_item_missing_file_and_desc_then_skipped(self) -> None:
        raw = '{"verdict": "changes_requested", "items": [{"severity": "info"}]}'

        result = ReviewResponseParser().parse(raw, "m")

        assert result.items == []

    def test_parse_when_json_suggestions_mixed_then_parsed(self) -> None:
        raw = (
            '{"verdict": "changes_requested", "suggestions": ["textual", '
            '{"description": "desc", "file": "a.py", "line": "3", "current_code": "x", "suggested_code": "y"}]}'
        )

        result = ReviewResponseParser().parse(raw, "m")

        assert len(result.suggestions) == 2
        assert result.suggestions[1].file_path == "a.py"

    def test_parse_when_json_praise_mixed_then_parsed(self) -> None:
        raw = '{"verdict": "changes_requested", "praise": ["textual", {"description": "desc", "file": "a.py"}]}'

        result = ReviewResponseParser().parse(raw, "m")

        assert len(result.praise) == 2
        assert result.praise[1].file_path == "a.py"

    def test_clean_response_when_stop_token_then_truncated(self) -> None:
        parser = ReviewResponseParser()

        cleaned = parser._clean_response('{"a": 1}<|im_end|>rest')

        assert cleaned == '{"a": 1}'

    def test_clean_response_when_code_block_then_inner(self) -> None:
        parser = ReviewResponseParser()

        cleaned = parser._clean_response('```json\n{"a": 1}\n```')

        assert cleaned == '{"a": 1}'

