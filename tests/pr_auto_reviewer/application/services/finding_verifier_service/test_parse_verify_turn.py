from ._helpers import *


class TestParseVerifyTurn:
    """Parsing a verification turn into results, tool call, or None."""

    def _verifier(self, mock_chat_port, mock_tool_factory) -> FindingVerifierService:
        return FindingVerifierService(
            mock_chat_port, "verify {findings}", mock_tool_factory
        )

    def test_returns_results_list(self, mock_chat_port, mock_tool_factory) -> None:
        assert self._verifier(
            mock_chat_port, mock_tool_factory
        )._parse_verify_turn('{"results": [{"finding_index": 1}]}') == [
            {"finding_index": 1}
        ]

    def test_returns_action_dict(self, mock_chat_port, mock_tool_factory) -> None:
        assert self._verifier(
            mock_chat_port, mock_tool_factory
        )._parse_verify_turn('{"action": "read_file"}') == {
            "action": "read_file"
        }

    def test_returns_none_for_non_dict_json(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        assert self._verifier(
            mock_chat_port, mock_tool_factory
        )._parse_verify_turn("[1, 2]") is None

    def test_returns_none_when_no_results_or_action(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        assert self._verifier(
            mock_chat_port, mock_tool_factory
        )._parse_verify_turn('{"foo": 1}') is None

    def test_delegates_to_prose_when_not_json(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        assert self._verifier(
            mock_chat_port, mock_tool_factory
        )._parse_verify_turn("narrative prose") is None

    def test_parses_action_dict_inside_markdown_code_fence(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        content = '```json\n{"action": "read_file", "args": "foo.py"}\n```'
        assert self._verifier(
            mock_chat_port, mock_tool_factory
        )._parse_verify_turn(content) == {
            "action": "read_file",
            "args": "foo.py",
        }

    def test_parses_action_dict_with_surrounding_prose(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        content = (
            'I will inspect the file:\n'
            '```json\n{"action": "read_file", "args": "foo.py"}\n```\n'
            'Awaiting output.'
        )
        assert self._verifier(
            mock_chat_port, mock_tool_factory
        )._parse_verify_turn(content) == {
            "action": "read_file",
            "args": "foo.py",
        }

    def test_parses_results_list_inside_markdown_code_fence(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        content = (
            '```json\n'
            '{"results": [{"finding_index": 0, "verified": true}]}\n'
            '```'
        )
        assert self._verifier(
            mock_chat_port, mock_tool_factory
        )._parse_verify_turn(content) == [
            {"finding_index": 0, "verified": True}
        ]

    def test_parses_raw_json_array_of_results(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        content = '[{"finding_index": 0, "verified": true}]'
        assert self._verifier(
            mock_chat_port, mock_tool_factory
        )._parse_verify_turn(content) == [
            {"finding_index": 0, "verified": True}
        ]

    def test_parses_raw_json_array_inside_markdown_code_fence(
        self, mock_chat_port, mock_tool_factory,
    ) -> None:
        content = '```json\n[{"finding_index": 0, "verified": true}]\n```'
        assert self._verifier(
            mock_chat_port, mock_tool_factory
        )._parse_verify_turn(content) == [
            {"finding_index": 0, "verified": True}
        ]

