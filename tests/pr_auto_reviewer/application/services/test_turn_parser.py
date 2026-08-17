"""Tests for TurnParser application service.

Uses a mocked ResponseParserPort so every branch of the parse logic
can be exercised without depending on the real parser's heuristics.
"""

from unittest.mock import MagicMock

from pr_auto_reviewer.application.services.turn_parser import TurnParser
from pr_auto_reviewer.domain.messages.commands.parse_review_turn_command import (
    ParseReviewTurnCommand,
)
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict


def _parser(
    *,
    items: list[dict] | None = None,
    observations: list[dict] | None = None,
    extracted_json: str | None = None,
    verdict: ReviewVerdict = ReviewVerdict.APPROVED,
    prose_suggestions: list[dict] | None = None,
    prose_praise: list[dict] | None = None,
) -> MagicMock:
    parser = MagicMock()
    parser.parse_items.return_value = items if items is not None else []
    parser.parse_item_observations.return_value = (
        observations if observations is not None else []
    )
    parser._sanitize_json_literals.side_effect = lambda text: text
    parser.extract_outermost_json.return_value = extracted_json
    parser._extract_verdict_md.return_value = verdict
    parser.parse_prose_recommendations.return_value = (
        prose_suggestions if prose_suggestions is not None else []
    )
    parser.parse_prose_praise.return_value = (
        prose_praise if prose_praise is not None else []
    )
    parser._normalize_item_dict.side_effect = lambda item: item
    parser.strip_frontmatter.side_effect = lambda text: text
    return parser


class TestTurnParser:
    """Behaviour of TurnParser._parse(content) -> TurnParseResult."""

    def test_execute_parses_command_content(self) -> None:
        parser = TurnParser(_parser())

        result = parser.execute(ParseReviewTurnCommand(content="not json"))

        assert result.kind == "unparseable"

    def test_verdict_with_items_merges_deduped_observations(self) -> None:
        stub = _parser(
            items=[{"description": "main issue"}],
            observations=[
                {"file": "a.py", "description": "new observation"},
                {"file": "", "description": "keep"},
            ],
        )
        parser = TurnParser(stub)

        result = parser._parse(
            '{"verdict":"approved","suggestions":[{"description":"keep"}]}'
        )

        assert result.kind == "verdict"
        assert result.raw_items == [{"description": "main issue"}]
        assert result.metadata is not None
        descriptions = [
            s["description"] for s in result.metadata["suggestions"]
        ]
        assert "new observation" in descriptions
        assert descriptions.count("keep") == 1

    def test_suggestions_as_dict_uses_nested_enhancements(self) -> None:
        parser = TurnParser(_parser())

        result = parser._parse(
            '{"verdict":"approved","suggestions":'
            '{"enhancements":[{"description":"a"},{"description":"b"}]}}'
        )

        assert result.kind == "verdict"
        assert result.metadata is not None
        assert [s["description"] for s in result.metadata["suggestions"]] == [
            "a",
            "b",
        ]

    def test_duplicate_suggestions_are_deduplicated(self) -> None:
        parser = TurnParser(_parser())

        result = parser._parse(
            '{"verdict":"approved","suggestions":'
            '[{"description":"dup"},{"description":"dup"}]}'
        )

        assert result.metadata is not None
        assert [s["description"] for s in result.metadata["suggestions"]] == [
            "dup"
        ]

    def test_suggestions_as_non_list_normalizes_to_empty(self) -> None:
        parser = TurnParser(_parser())

        result = parser._parse('{"verdict":"approved","suggestions":"text"}')

        assert result.metadata is not None
        assert result.metadata["suggestions"] == []

    def test_string_suggestions_are_normalized(self) -> None:
        parser = TurnParser(_parser())

        result = parser._parse(
            '{"verdict":"approved","suggestions":["do this","do that"]}'
        )

        assert result.metadata is not None
        assert result.metadata["suggestions"] == [
            {"file": "", "line": "", "description": "do this"},
            {"file": "", "line": "", "description": "do that"},
        ]

    def test_items_as_dict_yield_no_string_suggestions(self) -> None:
        parser = TurnParser(_parser())

        result = parser._parse('{"verdict":"approved","items":{"file":"a.py"}}')

        assert result.kind == "verdict"
        assert result.metadata is not None
        assert result.metadata["suggestions"] == []

    def test_unparseable_when_json_extraction_fails(self) -> None:
        parser = TurnParser(_parser(extracted_json=None))

        result = parser._parse("not json at all")

        assert result.kind == "unparseable"

    def test_unparseable_when_extracted_json_is_invalid(self) -> None:
        parser = TurnParser(_parser(extracted_json="{invalid"))

        result = parser._parse("not json at all")

        assert result.kind == "unparseable"

    def test_tool_call_extracted_from_prose_wrapper(self) -> None:
        stub = _parser(
            extracted_json='{"action":"read_file","args":{"file":"x.py"}}'
        )
        parser = TurnParser(stub)

        result = parser._parse("Here is the result:")

        assert result.kind == "tool_call"
        assert result.tool_call is not None
        assert result.tool_call.tool_name == "read_file"
        assert result.tool_call.arguments == {"args": "x.py"}

    def test_tool_call_with_list_args_joined(self) -> None:
        parser = TurnParser(_parser())

        result = parser._parse('{"action":"run_git","args":["status"]}')

        assert result.kind == "tool_call"
        assert result.tool_call is not None
        assert result.tool_call.arguments == {"args": "status"}

    def test_tool_call_with_dict_args_matching_action_key(self) -> None:
        parser = TurnParser(_parser())

        result = parser._parse(
            '{"action":"read_file","args":{"file":"src/a.py"}}'
        )

        assert result.tool_call is not None
        assert result.tool_call.arguments == {"args": "src/a.py"}

    def test_tool_call_with_dict_args_via_fallback(self) -> None:
        parser = TurnParser(_parser())

        result = parser._parse(
            '{"action":"mystery","args":{"file":"src/a.py"}}'
        )

        assert result.tool_call is not None
        assert result.tool_call.arguments == {"args": "src/a.py"}

    def test_tool_call_with_dict_args_no_match_returns_raw(self) -> None:
        parser = TurnParser(_parser())

        result = parser._parse('{"action":"mystery","args":{"foo":"bar"}}')

        assert result.tool_call is not None
        assert result.tool_call.arguments == {"args": "{'foo': 'bar'}"}

    def test_tool_call_with_scalar_args(self) -> None:
        parser = TurnParser(_parser())

        result = parser._parse('{"action":"run_git","args":"status"}')

        assert result.tool_call is not None
        assert result.tool_call.arguments == {"args": "status"}

    def test_list_json_parses_items_into_raw_items(self) -> None:
        parser = TurnParser(_parser())

        result = parser._parse(
            '[{"file":"a.py","description":"x"},{"file":"b.py","description":"y"}]'
        )

        assert result.kind == "verdict"
        assert result.raw_items == [
            {"file": "a.py", "description": "x"},
            {"file": "b.py", "description": "y"},
        ]
        assert result.metadata == {}

    def test_scalar_json_returns_unparseable(self) -> None:
        parser = TurnParser(_parser())

        result = parser._parse('"just a string"')

        assert result.kind == "unparseable"

    def test_verdict_metadata_from_markdown_when_no_json(self) -> None:
        stub = _parser(
            items=[{"description": "x"}],
            extracted_json=None,
            prose_suggestions=[{"description": "suggestion"}],
            prose_praise=[{"description": "praise"}],
        )
        parser = TurnParser(stub)

        result = parser._parse("not json")

        assert result.kind == "verdict"
        assert result.metadata is not None
        assert result.metadata["verdict"] == "approved"
        assert result.metadata["suggestions"] == [
            {"description": "suggestion"}
        ]
        assert result.metadata["praise"] == [{"description": "praise"}]

    def test_verdict_metadata_from_extracted_json(self) -> None:
        stub = _parser(
            items=[{"description": "x"}],
            extracted_json=(
                '{"verdict":"changes requested","reason":"because",'
                '"summary":"sum","suggestions":[{"description":"s"}],'
                '"praise":[{"description":"p"}]}'
            ),
        )
        parser = TurnParser(stub)

        result = parser._parse("prose")

        assert result.metadata is not None
        assert result.metadata["verdict"] == "changes_requested"
        assert result.metadata["reason"] == "because"
        assert result.metadata["summary"] == "sum"
        assert result.metadata["suggestions"] == [
            {"file": "", "line": "", "description": "s"}
        ]
        assert result.metadata["praise"] == [{"file": "", "description": "p"}]

    def test_verdict_metadata_falls_back_when_extracted_invalid(self) -> None:
        stub = _parser(items=[{"description": "x"}], extracted_json="{invalid")
        parser = TurnParser(stub)

        result = parser._parse("prose")

        assert result.metadata is not None
        assert result.metadata["verdict"] == "approved"

    def test_verdict_metadata_without_verdict_key_falls_back(self) -> None:
        stub = _parser(items=[{"description": "x"}])
        parser = TurnParser(stub)

        result = parser._parse('{"foo":"bar"}')

        assert result.metadata is not None
        assert result.metadata["verdict"] == "approved"

    def test_praise_as_non_list_normalizes_to_empty(self) -> None:
        parser = TurnParser(_parser())

        result = parser._parse('{"verdict":"approved","praise":"great"}')

        assert result.metadata is not None
        assert result.metadata["praise"] == []

    def test_string_items_become_suggestions(self) -> None:
        parser = TurnParser(_parser())

        result = parser._parse(
            '{"verdict":"approved","items":["Review this thing"]}'
        )

        assert result.metadata is not None
        assert result.metadata["suggestions"] == [
            {"file": "", "line": "", "description": "Review this thing"}
        ]

    def test_verdict_items_are_normalized_into_raw_items(self) -> None:
        parser = TurnParser(_parser())

        result = parser._parse(
            '{"verdict":"approved","items":[{"file":"a.py","description":"x"}]}'
        )

        assert result.kind == "verdict"
        assert result.raw_items == [{"file": "a.py", "description": "x"}]

    def test_praise_dict_and_string_entries_normalized(self) -> None:
        parser = TurnParser(_parser())

        result = parser._parse(
            '{"verdict":"approved","praise":'
            '[{"file":"a.py","description":"clean"},"nice"]}'
        )

        assert result.metadata is not None
        assert result.metadata["praise"] == [
            {"file": "a.py", "description": "clean"},
            {"file": "", "description": "nice"},
        ]
