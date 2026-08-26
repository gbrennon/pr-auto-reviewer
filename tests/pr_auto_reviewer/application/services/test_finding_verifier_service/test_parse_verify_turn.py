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

