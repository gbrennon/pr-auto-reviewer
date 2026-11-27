import json

from ._helpers import *


class TestTurnParserService:
    """Behaviour of TurnParserService._parse(content) -> TurnParseResult."""

    @staticmethod
    def _metadata(result: Any) -> dict[str, Any]:
        assert result.metadata is not None
        return result.metadata

    @staticmethod
    def _tool_call(result: Any) -> Any:
        assert result.tool_call is not None
        return result.tool_call

    def test_explicit_empty_envelope_is_a_verdict(self) -> None:
        content = json.dumps({
            "verdict": "approved",
            "reason": "No blocking issues found.",
            "summary": "The change is ready.",
            "items": [],
            "suggestions": [],
            "praise": [],
        })

        result = TurnParserService(ReviewResponseParser()).execute(
            ParseReviewTurnCommand(content=content)
        )

        assert result.kind is TurnKind.VERDICT
        assert result.raw_items == []
        assert self._metadata(result) == {
            "verdict": "approved",
            "reason": "No blocking issues found.",
            "summary": "The change is ready.",
            "suggestions": [],
            "praise": [],
        }

    def test_explicit_findings_and_alias_collections_are_preserved(self) -> None:
        content = json.dumps({
            "verdict": "changes_requested",
            "reason": "A blocking issue remains.",
            "summary": "One issue requires a fix.",
            "issues": [{
                "file": "x.py",
                "line": "4",
                "severity": "high",
                "category": "bug",
                "description": "The error is swallowed.",
                "suggested_fix": "",
            }],
            "recommendations": [{"file": "", "description": "Add a regression test."}],
            "strengths": ["Clear naming"],
        })

        result = TurnParserService(ReviewResponseParser()).execute(
            ParseReviewTurnCommand(content=content)
        )

        assert result.kind is TurnKind.VERDICT
        assert result.raw_items is not None
        assert result.raw_items[0]["severity"] == "major"
        assert self._metadata(result)["suggestions"][0]["description"] == (
            "Add a regression test."
        )
        assert self._metadata(result)["praise"][0]["description"] == "Clear naming"

    def test_missing_required_envelope_field_is_unparseable(self) -> None:
        base = {
            "verdict": "approved",
            "reason": "r",
            "summary": "s",
            "items": [],
            "suggestions": [],
            "praise": [],
        }
        for field in ("verdict", "reason", "summary", "items", "suggestions", "praise"):
            payload = {key: value for key, value in base.items() if key != field}
            result = TurnParserService(ReviewResponseParser()).execute(
                ParseReviewTurnCommand(content=json.dumps(payload))
            )
            assert result.kind is TurnKind.UNPARSEABLE

    def test_commented_or_unknown_verdict_is_unparseable(self) -> None:
        for verdict in ("commented", "not-a-verdict"):
            content = json.dumps({
                "verdict": verdict,
                "reason": "r",
                "summary": "s",
                "items": [],
                "suggestions": [],
                "praise": [],
            })

            result = TurnParserService(ReviewResponseParser()).execute(
                ParseReviewTurnCommand(content=content)
            )

            assert result.kind is TurnKind.UNPARSEABLE

    def test_malformed_item_is_unparseable(self) -> None:
        content = json.dumps({
            "verdict": "changes_requested",
            "reason": "r",
            "summary": "s",
            "items": [{
                "file": "x.py",
                "severity": "major",
                "category": "bug",
            }],
            "suggestions": [],
            "praise": [],
        })

        result = TurnParserService(ReviewResponseParser()).execute(
            ParseReviewTurnCommand(content=content)
        )

        assert result.kind is TurnKind.UNPARSEABLE

    def test_wrong_collection_type_or_empty_entry_is_unparseable(self) -> None:
        base = {
            "verdict": "approved",
            "reason": "r",
            "summary": "s",
            "items": [],
            "suggestions": [],
            "praise": [],
        }
        payloads = [
            {**base, "suggestions": {}},
            {**base, "praise": "good"},
            {**base, "suggestions": [""]},
            {**base, "praise": [{"description": ""}]},
        ]
        for payload in payloads:
            result = TurnParserService(ReviewResponseParser()).execute(
                ParseReviewTurnCommand(content=json.dumps(payload))
            )
            assert result.kind is TurnKind.UNPARSEABLE

    def test_list_only_json_is_unparseable(self) -> None:
        content = json.dumps([{
            "file": "x.py",
            "severity": "major",
            "category": "bug",
            "description": "A finding without an envelope.",
        }])

        result = TurnParserService(ReviewResponseParser()).execute(
            ParseReviewTurnCommand(content=content)
        )

        assert result.kind is TurnKind.UNPARSEABLE

    def test_wrapped_json_uses_the_same_strict_envelope(self) -> None:
        content = json.dumps({
            "status": "ok",
            "data": {
                "verdict": "approved",
                "reason": "r",
                "summary": "s",
                "items": [],
                "suggestions": [],
                "praise": [],
            },
        })

        result = TurnParserService(ReviewResponseParser()).execute(
            ParseReviewTurnCommand(content=content)
        )

        assert result.kind is TurnKind.VERDICT
        assert self._metadata(result)["summary"] == "s"

    def test_explicit_markdown_envelope_is_a_verdict(self) -> None:
        content = (
            "## Verdict\napproved\n\n"
            "**Reason:** No blocking issues found.\n\n"
            "## Summary\nThe change is ready.\n\n"
            "## Items\nNone\n\n"
            "## Suggestions\nNone\n\n"
            "## Praise\nNone"
        )

        result = TurnParserService(ReviewResponseParser()).execute(
            ParseReviewTurnCommand(content=content)
        )

        assert result.kind is TurnKind.VERDICT
        assert self._metadata(result)["verdict"] == "approved"

    def test_markdown_without_explicit_reason_is_unparseable(self) -> None:
        content = (
            "## Verdict\napproved\n\n"
            "## Summary\nThe change is ready.\n\n"
            "## Items\nNone\n\n"
            "## Suggestions\nNone\n\n"
            "## Praise\nNone"
        )

        result = TurnParserService(ReviewResponseParser()).execute(
            ParseReviewTurnCommand(content=content)
        )

        assert result.kind is TurnKind.UNPARSEABLE

    def test_tool_call_extracted_from_prose_wrapper(self) -> None:
        content = '```json\n{"action": "read_file", "args": {"path": "x.py"}}\n```'

        result = TurnParserService(ReviewResponseParser()).execute(
            ParseReviewTurnCommand(content=content)
        )

        assert result.kind is TurnKind.TOOL_CALL
        assert self._tool_call(result).tool_name == "read_file"

    def test_verdict_after_tool_call_json_is_not_discarded(self) -> None:
        content = (
            '```json\n{"action": "read_file", "args": "src/app.py"}\n```\n'
            '```json\n{"verdict": "approved", "reason": "clean", '
            '"summary": "No issues", "items": [], "suggestions": [], '
            '"praise": []}\n```'
        )
        parser = make_parser(extracted_json=None)
        result = TurnParserService(parser).execute(
            ParseReviewTurnCommand(content=content)
        )

        assert result.kind is TurnKind.VERDICT
        assert result.metadata is not None
        assert result.metadata["verdict"] == "approved"

    def test_read_file_tool_call_preserves_line_range(self) -> None:
        content = (
            '```json\n{"action": "read_file", "args": "src/app.py", '
            '"line_range": [2, 3]}\n```'
        )
        extracted = (
            '{"action": "read_file", "args": "src/app.py", '
            '"line_range": [2, 3]}'
        )
        parser = make_parser(extracted_json=extracted)
        result = TurnParserService(parser).execute(
            ParseReviewTurnCommand(content=content)
        )

        assert result.kind is TurnKind.TOOL_CALL
        assert result.tool_call is not None
        assert result.tool_call.arguments == {
            "args": "src/app.py",
            "line_range": [2, 3],
        }

    def test_tool_call_with_list_args_joined(self) -> None:
        content = '```json\n{"action": "cmd", "args": ["arg1", "arg2"]}\n```'

        result = TurnParserService(ReviewResponseParser()).execute(
            ParseReviewTurnCommand(content=content)
        )

        assert result.kind is TurnKind.TOOL_CALL
        assert "arg1" in self._tool_call(result).arguments["args"]
        assert "arg2" in self._tool_call(result).arguments["args"]

    def test_tool_call_with_dict_args_matching_action_key(self) -> None:
        content = (
            '```json\n{"action": "edit", '
            '"args": {"action": "edit", "file": "x.py"}}\n```'
        )

        result = TurnParserService(ReviewResponseParser()).execute(
            ParseReviewTurnCommand(content=content)
        )

        assert result.kind is TurnKind.TOOL_CALL
        assert self._tool_call(result).tool_name == "edit"

    def test_tool_call_with_dict_args_via_fallback(self) -> None:
        content = '```json\n{"action": "edit", "args": {"file": "x.py"}}\n```'

        result = TurnParserService(ReviewResponseParser()).execute(
            ParseReviewTurnCommand(content=content)
        )

        assert result.kind is TurnKind.TOOL_CALL
        assert self._tool_call(result).arguments["args"] == "x.py"

    def test_tool_call_with_dict_args_no_match_returns_raw(self) -> None:
        content = '```json\n{"action": "custom", "args": {"foo": "bar"}}\n```'

        result = TurnParserService(ReviewResponseParser()).execute(
            ParseReviewTurnCommand(content=content)
        )

        assert result.kind is TurnKind.TOOL_CALL
        assert "foo" in self._tool_call(result).arguments["args"]

    def test_tool_call_with_scalar_args(self) -> None:
        content = '```json\n{"action": "run", "args": "echo hello"}\n```'

        result = TurnParserService(ReviewResponseParser()).execute(
            ParseReviewTurnCommand(content=content)
        )

        assert result.kind is TurnKind.TOOL_CALL
        assert "echo hello" in self._tool_call(result).arguments["args"]
