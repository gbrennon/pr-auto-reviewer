from ._helpers import *


class TestClassifyTurn:
    """Exercises the per-line turn classifier."""

    def test_classify_when_tool_calls_then_tool_call(self) -> None:
        assert (
            _client()._classify_turn("", {"tool_calls": [{"function": {"name": "read_file"}}]}, False)
            == "tool_call"
        )

    def test_classify_when_verdict_marker_then_verdict(self) -> None:
        assert _client()._classify_turn("verdict: approved", {}, False) == "verdict"

    def test_classify_when_verbatim_verdict_then_verdict(self) -> None:
        assert _client()._classify_turn("approved", {}, False) == "verdict"

    def test_classify_when_json_object_then_complete(self) -> None:
        assert _client()._classify_turn('{"a": 1}', {}, False) == "complete"

    def test_classify_when_json_array_then_complete(self) -> None:
        assert _client()._classify_turn("[1, 2]", {}, False) == "complete"

    def test_classify_when_other_then_unparseable(self) -> None:
        assert _client()._classify_turn("filler", {}, False) == "unparseable"

    def test_classify_when_verdict_seen_then_verdict_not_reclassified(self) -> None:
        assert _client()._classify_turn("verdict: approved", {}, True) == "unparseable"
