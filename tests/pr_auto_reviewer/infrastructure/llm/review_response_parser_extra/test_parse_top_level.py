import json
from ._helpers import *


class TestParseTopLevel:
    """Exercises the public parse() entry point end to end."""

    def test_parse_when_json_with_stop_token_then_parsed(self) -> None:
        raw = (
            '{"verdict": "approved", "reason": "r", "summary": "s", '
            '"items": [], "suggestions": [], "praise": []}<|im_end|>'
        )

        result = ReviewResponseParser().parse(raw, "m")

        assert result.verdict == ReviewVerdict.APPROVED
        assert result.items == []
        assert result.suggestions == []
        assert result.praise == []

    def test_parse_when_json_in_code_block_then_parsed(self) -> None:
        raw = (
            '```json\n{"verdict": "changes_requested", "reason": "r", '
            '"summary": "s", "items": [], "suggestions": [], "praise": []}\n```'
        )

        result = ReviewResponseParser().parse(raw, "m")

        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED

    def test_parse_when_embedded_json_then_extracted(self) -> None:
        raw = (
            'note {"verdict": "approved", "reason": "r", "summary": "fine", '
            '"items": [], "suggestions": [], "praise": []} note'
        )

        result = ReviewResponseParser().parse(raw, "m")

        assert result.verdict == ReviewVerdict.APPROVED

    def test_parse_when_json_item_has_explicit_fields_then_parsed(self) -> None:
        raw = (
            '{"verdict": "changes_requested", "reason": "r", "summary": "s", '
            '"items": [{"file": "a.py", "category": "quality", '
            '"description": "unused var", "severity": "high"}], '
            '"suggestions": [], "praise": []}'
        )

        result = ReviewResponseParser().parse(raw, "m")

        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert result.items[0].file_path == "a.py"
        assert result.items[0].description == "unused var"
        assert result.items[0].suggested_fix == ""

    def test_parse_when_json_item_missing_description_then_rejected(self) -> None:
        raw = (
            '{"verdict": "changes_requested", "reason": "r", "summary": "s", '
            '"items": [{"file": "a.py", "category": "quality", "severity": "info"}], '
            '"suggestions": [], "praise": []}'
        )

        with pytest.raises(ReviewVerdictError):
            ReviewResponseParser().parse(raw, "m")

    def test_parse_when_json_suggestions_mixed_then_parsed(self) -> None:
        raw = (
            '{"verdict": "changes_requested", "reason": "r", "summary": "s", '
            '"items": [], "suggestions": ["textual", '
            '{"description": "desc", "file": "a.py", "line": "3", '
            '"current_code": "x", "suggested_code": "y"}], "praise": []}'
        )

        result = ReviewResponseParser().parse(raw, "m")

        assert len(result.suggestions) == 2
        assert result.suggestions[1].file_path == "a.py"

    def test_parse_when_json_praise_mixed_then_parsed(self) -> None:
        raw = (
            '{"verdict": "changes_requested", "reason": "r", "summary": "s", '
            '"items": [], "suggestions": [], "praise": '
            '["textual", {"description": "desc", "file": "a.py"}]}'
        )

        result = ReviewResponseParser().parse(raw, "m")

        assert len(result.praise) == 2
        assert result.praise[1].file_path == "a.py"

    def test_parse_when_missing_verdict_then_rejected(self) -> None:
        raw = (
            '{"reason": "r", "summary": "s", "items": [], '
            '"suggestions": [], "praise": []}'
        )

        with pytest.raises(ReviewVerdictError):
            ReviewResponseParser().parse(raw, "m")

    def test_parse_when_unknown_verdict_then_rejected(self) -> None:
        raw = (
            '{"verdict": "commented", "reason": "r", "summary": "s", '
            '"items": [], "suggestions": [], "praise": []}'
        )

        with pytest.raises(ReviewVerdictError):
            ReviewResponseParser().parse(raw, "m")

    def test_parse_when_missing_reason_or_summary_then_rejected(self) -> None:
        for field in ("reason", "summary"):
            payload = {
                "verdict": "approved",
                "reason": "r",
                "summary": "s",
                "items": [],
                "suggestions": [],
                "praise": [],
            }
            payload[field] = ""

            with pytest.raises(ReviewVerdictError):
                ReviewResponseParser().parse(json.dumps(payload), "m")

    def test_parse_when_findings_collection_missing_or_not_list_then_rejected(self) -> None:
        missing = {
            "verdict": "approved",
            "reason": "r",
            "summary": "s",
            "suggestions": [],
            "praise": [],
        }
        wrong_type = {
            **missing,
            "items": {},
        }

        with pytest.raises(ReviewVerdictError):
            ReviewResponseParser().parse(json.dumps(missing), "m")
        with pytest.raises(ReviewVerdictError):
            ReviewResponseParser().parse(json.dumps(wrong_type), "m")

    def test_parse_when_suggestions_or_praise_missing_or_empty_entry_then_rejected(self) -> None:
        base = {
            "verdict": "approved",
            "reason": "r",
            "summary": "s",
            "items": [],
            "suggestions": [],
            "praise": [],
        }
        for field in ("suggestions", "praise"):
            missing = {key: value for key, value in base.items() if key != field}
            empty_entry = {**base, field: [""]}

            with pytest.raises(ReviewVerdictError):
                ReviewResponseParser().parse(json.dumps(missing), "m")
            with pytest.raises(ReviewVerdictError):
                ReviewResponseParser().parse(json.dumps(empty_entry), "m")

    def test_parse_when_markdown_envelope_is_explicit_then_parsed(self) -> None:
        raw = (
            "## Verdict\napproved\n\n"
            "**Reason:** No blocking issues were found.\n\n"
            "## Summary\nThe change is ready.\n\n"
            "## Items\nNone\n\n"
            "## Suggestions\nNone\n\n"
            "## Praise\nNone"
        )

        result = ReviewResponseParser().parse(raw, "m")

        assert result.verdict == ReviewVerdict.APPROVED
        assert result.reason == "No blocking issues were found."
        assert result.summary == "The change is ready."
        assert result.items == []
        assert result.suggestions == []
        assert result.praise == []

    def test_parse_when_markdown_envelope_is_missing_reason_then_rejected(self) -> None:
        raw = (
            "## Verdict\napproved\n\n"
            "## Summary\nThe change is ready.\n\n"
            "## Items\nNone\n\n"
            "## Suggestions\nNone\n\n"
            "## Praise\nNone"
        )

        with pytest.raises(ReviewVerdictError):
            ReviewResponseParser().parse(raw, "m")

    def test_clean_response_when_stop_token_then_truncated(self) -> None:
        parser = ReviewResponseParser()

        cleaned = parser._clean_response('{"a": 1}<|im_end|>rest')

        assert cleaned == '{"a": 1}'

    def test_clean_response_when_code_block_then_inner(self) -> None:
        parser = ReviewResponseParser()

        cleaned = parser._clean_response('```json\n{"a": 1}\n```')

        assert cleaned == '{"a": 1}'
