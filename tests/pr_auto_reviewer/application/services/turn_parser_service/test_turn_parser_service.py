from ._helpers import *


class TestTurnParserService:
    """Behaviour of TurnParserService._parse(content) -> TurnParseResult."""
    @staticmethod
    def _raw_items(result: Any) -> list[dict[str, Any]]:
        assert result.raw_items is not None
        return result.raw_items

    @staticmethod
    def _metadata(result: Any) -> dict[str, Any]:
        assert result.metadata is not None
        return result.metadata

    @staticmethod
    def _tool_call(result: Any) -> Any:
        assert result.tool_call is not None
        return result.tool_call


    def test_execute_parses_command_content(self) -> None:
        parser = make_parser(items=[{"file": "x.py", "severity": "major"}])
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content="any")
        result = service.execute(command)

        assert result.kind is TurnKind.VERDICT
        assert len(self._raw_items(result)) == 1

    def test_verdict_with_items_merges_deduped_observations(self) -> None:
        items = [{"file": "x.py", "severity": "major", "description": "dup"}]
        observations = [{"file": "x.py", "severity": "major", "description": "dup"}]
        parser = make_parser(items=items, observations=observations)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content="any")
        result = service.execute(command)

        assert result.kind is TurnKind.VERDICT
        assert len(self._raw_items(result)) == 1
        assert len(self._metadata(result).get("suggestions", [])) >= 1

    def test_suggestions_as_dict_uses_nested_enhancements(self) -> None:
        items = [{"file": "x.py", "severity": "major"}]
        prose_suggestions = [
            {"file": "y.py", "description": "nested"},
            {"file": "z.py", "description": "also nested"},
        ]
        parser = make_parser(items=items, prose_suggestions=prose_suggestions)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content="any")
        result = service.execute(command)

        assert result.kind is TurnKind.VERDICT
        assert len(self._metadata(result).get("suggestions", [])) == 2

    def test_duplicate_observations_are_deduplicated(self) -> None:
        items = [{"file": "x.py", "severity": "major"}]
        prose_suggestions = [{"file": "y.py", "description": "same"}]
        observations = [
            {"file": "y.py", "description": "same"},
            {"file": "z.py", "description": "other"},
        ]
        parser = make_parser(
            items=items, prose_suggestions=prose_suggestions,
            observations=observations,
        )
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content="any")
        result = service.execute(command)

        suggestions = self._metadata(result).get("suggestions", [])
        assert len(suggestions) == 2
        assert {"file": "y.py", "description": "same"} in suggestions

    def test_suggestions_as_non_list_normalizes_to_empty(self) -> None:
        items = [{"file": "x.py", "severity": "major"}]
        parser = make_parser(items=items, prose_suggestions=[])
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content="any")
        result = service.execute(command)

        assert self._metadata(result).get("suggestions") == []

    def test_string_suggestions_are_normalized(self) -> None:
        items = [{"file": "x.py", "severity": "major"}]
        parser = make_parser(items=items, prose_suggestions=[{"description": "string suggestion"}])
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content="any")
        result = service.execute(command)

        suggestions = self._metadata(result).get("suggestions", [])
        assert len(suggestions) == 1

    def test_items_as_dict_yield_no_string_suggestions(self) -> None:
        items = [{"file": "x.py", "severity": "major"}]
        parser = make_parser(items=items)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content="any")
        result = service.execute(command)

        assert self._metadata(result).get("suggestions") == []

    def test_unparseable_when_json_extraction_fails(self) -> None:
        parser = make_parser(extracted_json=None)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content="not json at all")
        result = service.execute(command)

        assert result.kind is TurnKind.UNPARSEABLE

    def test_unparseable_when_extracted_json_is_invalid(self) -> None:
        parser = make_parser(extracted_json="invalid json {")
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content="text")
        result = service.execute(command)

        assert result.kind is TurnKind.UNPARSEABLE

    def test_tool_call_extracted_from_prose_wrapper(self) -> None:
        content = '```json\n{"action": "read_file", "args": {"path": "x.py"}}\n```'
        extracted = '{"action": "read_file", "args": {"path": "x.py"}}'
        parser = make_parser(extracted_json=extracted)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind is TurnKind.TOOL_CALL
        assert result.tool_call is not None
        assert result.tool_call.tool_name == "read_file"

    def test_tool_call_with_list_args_joined(self) -> None:
        content = '```json\n{"action": "cmd", "args": ["arg1", "arg2"]}\n```'
        extracted = '{"action": "cmd", "args": ["arg1", "arg2"]}'
        parser = make_parser(extracted_json=extracted)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind is TurnKind.TOOL_CALL
        assert "arg1" in self._tool_call(result).arguments["args"]
        assert "arg2" in self._tool_call(result).arguments["args"]

    def test_tool_call_with_dict_args_matching_action_key(self) -> None:
        content = (
            '```json\n{"action": "edit", "args": {"action": "edit", "file": "x.py"}}\n```'
        )
        extracted = '{"action": "edit", "args": {"action": "edit", "file": "x.py"}}'
        parser = make_parser(extracted_json=extracted)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind is TurnKind.TOOL_CALL
        assert self._tool_call(result).tool_name == "edit"

    def test_tool_call_with_dict_args_via_fallback(self) -> None:
        content = '```json\n{"action": "edit", "args": {"file": "x.py"}}\n```'
        extracted = '{"action": "edit", "args": {"file": "x.py"}}'
        parser = make_parser(extracted_json=extracted)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind is TurnKind.TOOL_CALL
        assert self._tool_call(result).arguments["args"] == "x.py"

    def test_tool_call_with_dict_args_no_match_returns_raw(self) -> None:
        content = '```json\n{"action": "custom", "args": {"foo": "bar"}}\n```'
        extracted = '{"action": "custom", "args": {"foo": "bar"}}'
        parser = make_parser(extracted_json=extracted)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind is TurnKind.TOOL_CALL
        assert "foo" in self._tool_call(result).arguments["args"]

    def test_tool_call_with_scalar_args(self) -> None:
        content = '```json\n{"action": "run", "args": "echo hello"}\n```'
        extracted = '{"action": "run", "args": "echo hello"}'
        parser = make_parser(extracted_json=extracted)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind is TurnKind.TOOL_CALL
        assert "echo hello" in self._tool_call(result).arguments["args"]

    def test_list_json_parses_items_into_raw_items(self) -> None:
        content = '[{"file": "x.py", "severity": "major"}]'
        parser = make_parser()
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind is TurnKind.VERDICT
        assert len(self._raw_items(result)) == 1

    def test_scalar_json_returns_unparseable(self) -> None:
        content = '"just a string"'
        parser = make_parser()
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind is TurnKind.UNPARSEABLE

    def test_verdict_metadata_from_markdown_when_no_json(self) -> None:
        content = "## Verdict\napproved\n\n## Summary\nlooks good"
        items = [{"file": "x.py", "severity": "major"}]
        parser = make_parser(items=items, verdict=ReviewVerdict.APPROVED)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind is TurnKind.VERDICT
        assert self._metadata(result)["verdict"] == "approved"

    def test_verdict_metadata_from_extracted_json(self) -> None:
        content = '```json\n{"verdict": "changes_requested"}\n```'
        parser = make_parser(
            extracted_json='{"verdict": "changes_requested"}',
            verdict=ReviewVerdict.CHANGES_REQUESTED,
        )
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind is TurnKind.VERDICT
        assert self._metadata(result)["verdict"] == "changes_requested"

    def test_verdict_metadata_falls_back_when_extracted_invalid(self) -> None:
        content = '```json\nnot valid json\n```'
        items = [{"file": "x.py", "severity": "major"}]
        parser = make_parser(items=items, verdict=ReviewVerdict.CHANGES_REQUESTED)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind is TurnKind.VERDICT
        assert self._metadata(result)["verdict"] == "changes_requested"

    def test_verdict_metadata_without_verdict_key_falls_back(self) -> None:
        content = '```json\n{"summary": "only summary"}\n```'
        items = [{"file": "x.py", "severity": "major"}]
        parser = make_parser(items=items, verdict=ReviewVerdict.APPROVED)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind is TurnKind.VERDICT
        assert self._metadata(result)["verdict"] == "approved"

    def test_praise_as_non_list_normalizes_to_empty(self) -> None:
        items = [{"file": "x.py", "severity": "major"}]
        parser = make_parser(items=items, prose_praise=[])
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content="any")
        result = service.execute(command)

        assert self._metadata(result).get("praise") == []

    def test_string_items_become_suggestions(self) -> None:
        content = '{"verdict": "approved", "items": ["string item"]}'
        parser = make_parser()
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        suggestions = self._metadata(result).get("suggestions", [])
        assert len(suggestions) == 1

    def test_verdict_items_are_normalized_into_raw_items(self) -> None:
        content = '{"verdict": "approved", "items": [{"file": "x.py", "severity": "major"}]}'
        parser = make_parser()
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind is TurnKind.VERDICT
        assert len(self._raw_items(result)) == 1
        assert self._raw_items(result)[0]["file"] == "x.py"

    def test_praise_dict_and_string_entries_normalized(self) -> None:
        items = [{"file": "x.py", "severity": "major"}]
        prose_praise = [
            {"file": "y.py", "description": "dict praise"},
            {"description": "string praise"},
        ]
        parser = make_parser(items=items, prose_praise=prose_praise)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content="any")
        result = service.execute(command)

        praise = self._metadata(result).get("praise", [])
        assert len(praise) == 2

    def test_pure_suggestions_and_praise_json_parsed(self) -> None:
        content = (
            '{"suggestions": [{"file": "a.py", "description": "Reduce class size"}], '
            '"praise": [{"file": "b.py", "description": "Clean composition"}]}'
        )
        parser = make_parser()
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind is TurnKind.VERDICT
        assert len(self._metadata(result).get("suggestions", [])) == 1
        assert self._metadata(result)["suggestions"][0]["description"] == "Reduce class size"
        assert len(self._metadata(result).get("praise", [])) == 1
        assert self._metadata(result)["praise"][0]["description"] == "Clean composition"

    def test_wrapped_data_suggestions_and_praise_parsed(self) -> None:
        content = (
            '{"status": "ok", "data": {'
            '"suggestions": [{"file": "validator.py", "description": "Extract helper"}], '
            '"praise": [{"file": "validator.py", "description": "Solid type hints"}]}}'
        )
        parser = make_parser()
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind is TurnKind.VERDICT
        metadata = self._metadata(result)
        assert len(metadata.get("suggestions", [])) == 1
        assert metadata["suggestions"][0]["description"] == "Extract helper"
        assert len(metadata.get("praise", [])) == 1
        assert metadata["praise"][0]["description"] == "Solid type hints"

    def test_wrapped_data_items_and_verdict_parsed(self) -> None:
        content = (
            '{"status": "ok", "data": {'
            '"items": [{"file": "x.py", "line": "10", "severity": "critical", "description": "Null deref"}], '
            '"verdict": "changes_requested", '
            '"reason": "Null dereference found", '
            '"suggestions": [], "praise": []}}'
        )
        parser = make_parser(items=[{"file": "x.py", "line": "10", "severity": "critical", "description": "Null deref"}])
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind is TurnKind.VERDICT
        assert len(self._raw_items(result)) == 1
        assert self._metadata(result)["verdict"] == "changes_requested"
        assert self._metadata(result)["reason"] == "Null dereference found"

