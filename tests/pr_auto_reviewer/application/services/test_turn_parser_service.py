"""Tests for TurnParserService application service.

Uses a fake parser so every branch of the parse logic
can be exercised without depending on the real parser's heuristics.
"""

import json
from typing import Any

from pr_auto_reviewer.application.services.turn_parser_service import TurnParserService
from pr_auto_reviewer.domain.messages.commands.parse_review_turn_command import (
    ParseReviewTurnCommand,
)
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)


class FakeResponseParser:
    """Fake parser implementation for testing TurnParserService."""

    def __init__(
        self,
        *,
        items: list[dict] | None = None,
        observations: list[dict] | None = None,
        extracted_json: str | None = None,
        verdict: ReviewVerdict = ReviewVerdict.APPROVED,
        prose_suggestions: list[dict] | None = None,
        prose_praise: list[dict] | None = None,
    ) -> None:
        self._items = items if items is not None else []
        self._observations = observations if observations is not None else []
        self._extracted_json = extracted_json
        self._verdict = verdict
        self._prose_suggestions = prose_suggestions if prose_suggestions is not None else []
        self._prose_praise = prose_praise if prose_praise is not None else []

    def parse_items(self, raw_text: str) -> list[dict[str, Any]]:
        return self._items

    def parse_item_observations(self, raw_text: str) -> list[dict[str, Any]]:
        return self._observations

    def sanitize_json_literals(self, text: str) -> str:
        return text

    def extract_outermost_json(self, text: str) -> str | None:
        return self._extracted_json

    def extract_verdict_md(self, raw_text: str) -> ReviewVerdict:
        return self._verdict

    def parse_prose_recommendations(self, raw_text: str) -> list[dict[str, Any]]:
        return self._prose_suggestions

    def parse_prose_praise(self, raw_text: str) -> list[dict[str, Any]]:
        return self._prose_praise

    def normalize_item_dict(self, item: dict[str, Any]) -> dict[str, Any]:
        return item

    def strip_frontmatter(self, text: str) -> str:
        return text


def make_parser(
    *,
    items: list[dict] | None = None,
    observations: list[dict] | None = None,
    extracted_json: str | None = None,
    verdict: ReviewVerdict = ReviewVerdict.APPROVED,
    prose_suggestions: list[dict] | None = None,
    prose_praise: list[dict] | None = None,
) -> FakeResponseParser:
    """Create a configured fake parser for testing."""
    return FakeResponseParser(
        items=items,
        observations=observations,
        extracted_json=extracted_json,
        verdict=verdict,
        prose_suggestions=prose_suggestions,
        prose_praise=prose_praise,
    )


class TestTurnParserService:
    """Behaviour of TurnParserService._parse(content) -> TurnParseResult."""

    def test_execute_parses_command_content(self) -> None:
        parser = make_parser(items=[{"file": "x.py", "severity": "major"}])
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content="any")
        result = service.execute(command)

        assert result.kind == "verdict"
        assert len(result.raw_items) == 1

    def test_verdict_with_items_merges_deduped_observations(self) -> None:
        items = [{"file": "x.py", "severity": "major", "description": "dup"}]
        observations = [{"file": "x.py", "severity": "major", "description": "dup"}]
        parser = make_parser(items=items, observations=observations)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content="any")
        result = service.execute(command)

        assert result.kind == "verdict"
        assert len(result.raw_items) == 1
        assert len(result.metadata.get("suggestions", [])) >= 1

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

        assert result.kind == "verdict"
        assert len(result.metadata.get("suggestions", [])) == 2

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

        suggestions = result.metadata.get("suggestions", [])
        assert len(suggestions) == 2
        assert {"file": "y.py", "description": "same"} in suggestions

    def test_suggestions_as_non_list_normalizes_to_empty(self) -> None:
        items = [{"file": "x.py", "severity": "major"}]
        parser = make_parser(items=items, prose_suggestions=[])
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content="any")
        result = service.execute(command)

        assert result.metadata.get("suggestions") == []

    def test_string_suggestions_are_normalized(self) -> None:
        items = [{"file": "x.py", "severity": "major"}]
        parser = make_parser(items=items, prose_suggestions=[{"description": "string suggestion"}])
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content="any")
        result = service.execute(command)

        suggestions = result.metadata.get("suggestions", [])
        assert len(suggestions) == 1

    def test_items_as_dict_yield_no_string_suggestions(self) -> None:
        items = [{"file": "x.py", "severity": "major"}]
        parser = make_parser(items=items)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content="any")
        result = service.execute(command)

        assert result.metadata.get("suggestions") == []

    def test_unparseable_when_json_extraction_fails(self) -> None:
        parser = make_parser(extracted_json=None)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content="not json at all")
        result = service.execute(command)

        assert result.kind == "unparseable"

    def test_unparseable_when_extracted_json_is_invalid(self) -> None:
        parser = make_parser(extracted_json="invalid json {")
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content="text")
        result = service.execute(command)

        assert result.kind == "unparseable"

    def test_tool_call_extracted_from_prose_wrapper(self) -> None:
        content = '```json\n{"action": "read_file", "args": {"path": "x.py"}}\n```'
        extracted = '{"action": "read_file", "args": {"path": "x.py"}}'
        parser = make_parser(extracted_json=extracted)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind == "tool_call"
        assert result.tool_call is not None
        assert result.tool_call.tool_name == "read_file"

    def test_tool_call_with_list_args_joined(self) -> None:
        content = '```json\n{"action": "cmd", "args": ["arg1", "arg2"]}\n```'
        extracted = '{"action": "cmd", "args": ["arg1", "arg2"]}'
        parser = make_parser(extracted_json=extracted)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind == "tool_call"
        assert "arg1" in result.tool_call.arguments["args"]
        assert "arg2" in result.tool_call.arguments["args"]

    def test_tool_call_with_dict_args_matching_action_key(self) -> None:
        content = (
            '```json\n{"action": "edit", "args": {"action": "edit", "file": "x.py"}}\n```'
        )
        extracted = '{"action": "edit", "args": {"action": "edit", "file": "x.py"}}'
        parser = make_parser(extracted_json=extracted)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind == "tool_call"
        assert result.tool_call.tool_name == "edit"

    def test_tool_call_with_dict_args_via_fallback(self) -> None:
        content = '```json\n{"action": "edit", "args": {"file": "x.py"}}\n```'
        extracted = '{"action": "edit", "args": {"file": "x.py"}}'
        parser = make_parser(extracted_json=extracted)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind == "tool_call"
        assert result.tool_call.arguments["args"] == "x.py"

    def test_tool_call_with_dict_args_no_match_returns_raw(self) -> None:
        content = '```json\n{"action": "custom", "args": {"foo": "bar"}}\n```'
        extracted = '{"action": "custom", "args": {"foo": "bar"}}'
        parser = make_parser(extracted_json=extracted)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind == "tool_call"
        assert "foo" in result.tool_call.arguments["args"]

    def test_tool_call_with_scalar_args(self) -> None:
        content = '```json\n{"action": "run", "args": "echo hello"}\n```'
        extracted = '{"action": "run", "args": "echo hello"}'
        parser = make_parser(extracted_json=extracted)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind == "tool_call"
        assert "echo hello" in result.tool_call.arguments["args"]

    def test_list_json_parses_items_into_raw_items(self) -> None:
        content = '[{"file": "x.py", "severity": "major"}]'
        parser = make_parser()
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind == "verdict"
        assert len(result.raw_items) == 1

    def test_scalar_json_returns_unparseable(self) -> None:
        content = '"just a string"'
        parser = make_parser()
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind == "unparseable"

    def test_verdict_metadata_from_markdown_when_no_json(self) -> None:
        content = "## Verdict\napproved\n\n## Summary\nlooks good"
        items = [{"file": "x.py", "severity": "major"}]
        parser = make_parser(items=items, verdict=ReviewVerdict.APPROVED)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind == "verdict"
        assert result.metadata["verdict"] == "approved"

    def test_verdict_metadata_from_extracted_json(self) -> None:
        content = '```json\n{"verdict": "changes_requested"}\n```'
        parser = make_parser(
            extracted_json='{"verdict": "changes_requested"}',
            verdict=ReviewVerdict.CHANGES_REQUESTED,
        )
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind == "verdict"
        assert result.metadata["verdict"] == "changes_requested"

    def test_verdict_metadata_falls_back_when_extracted_invalid(self) -> None:
        content = '```json\nnot valid json\n```'
        items = [{"file": "x.py", "severity": "major"}]
        parser = make_parser(items=items, verdict=ReviewVerdict.CHANGES_REQUESTED)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind == "verdict"
        assert result.metadata["verdict"] == "changes_requested"

    def test_verdict_metadata_without_verdict_key_falls_back(self) -> None:
        content = '```json\n{"summary": "only summary"}\n```'
        items = [{"file": "x.py", "severity": "major"}]
        parser = make_parser(items=items, verdict=ReviewVerdict.APPROVED)
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind == "verdict"
        assert result.metadata["verdict"] == "approved"

    def test_praise_as_non_list_normalizes_to_empty(self) -> None:
        items = [{"file": "x.py", "severity": "major"}]
        parser = make_parser(items=items, prose_praise=[])
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content="any")
        result = service.execute(command)

        assert result.metadata.get("praise") == []

    def test_string_items_become_suggestions(self) -> None:
        content = '{"verdict": "approved", "items": ["string item"]}'
        parser = make_parser()
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        suggestions = result.metadata.get("suggestions", [])
        assert len(suggestions) == 1

    def test_verdict_items_are_normalized_into_raw_items(self) -> None:
        content = '{"verdict": "approved", "items": [{"file": "x.py", "severity": "major"}]}'
        parser = make_parser()
        service = TurnParserService(parser)
        command = ParseReviewTurnCommand(content=content)
        result = service.execute(command)

        assert result.kind == "verdict"
        assert len(result.raw_items) == 1
        assert result.raw_items[0]["file"] == "x.py"

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

        praise = result.metadata.get("praise", [])
        assert len(praise) == 2


class TestTurnParserServiceItemExtraction:
    """TurnParserService must pass normalized item dicts into raw_items."""

    def test_verdict_branch_normalizes_issue_items(self) -> None:
        parser = TurnParserService(ReviewResponseParser())
        result = parser.execute(ParseReviewTurnCommand(content=json.dumps({
            "verdict": "Needs Improvement",
            "reason": "lacks error handling",
            "items": [
                {"file": "src/a.py", "issue": "No error handling.",
                 "severity": "High"},
            ],
        })))
        assert result.kind == "verdict"
        assert result.metadata is not None
        assert len(result.raw_items or []) == 1
        assert result.raw_items[0]["description"] == "No error handling."
        assert result.raw_items[0]["severity"] == "major"

    def test_verdict_branch_keeps_string_items_out_of_raw_items(self) -> None:
        parser = TurnParserService(ReviewResponseParser())
        result = parser.execute(ParseReviewTurnCommand(content=json.dumps({
            "verdict": "approved",
            "items": ["Review multi_phase_orchestrator.py"],
        })))
        assert result.kind == "verdict"
        assert result.raw_items == []
        assert result.metadata is not None
        assert result.metadata["suggestions"] != []

    def test_positive_verdict_coerces_to_approved(self) -> None:
        parser = TurnParserService(ReviewResponseParser())
        result = parser.execute(ParseReviewTurnCommand(content=json.dumps({
            "verdict": "Positive",
            "reason": "codebase is clean",
            "items": [],
        })))
        assert result.metadata is not None
        assert result.metadata["verdict"] == "approved"

    def test_no_issues_found_coerces_to_approved(self) -> None:
        parser = TurnParserService(ReviewResponseParser())
        result = parser.execute(ParseReviewTurnCommand(content=json.dumps({
            "verdict": "no_issues_found",
            "items": [],
        })))
        assert result.metadata is not None
        assert result.metadata["verdict"] == "approved"
