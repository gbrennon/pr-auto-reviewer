from ._helpers import *


class TestOllamaReviewStream:
    """Exercises the review stream container."""

    def test_defaults_when_created_then_initial_state(self) -> None:
        stream = OllamaReviewStream()

        assert stream.turn_number == 1
        assert stream.content == ""
        assert stream.kind == "initial"
        assert stream.parsed is None
        assert stream.items is None
        assert stream.metadata["verdict"] == "commented"

    def test_advance_when_complete_valid_json_then_populates(self) -> None:
        stream = OllamaReviewStream()

        stream.advance(
            '{"verdict": "approved", "items": [{"file": "a.py"}]}',
            "complete",
        )

        assert stream.kind == "complete"
        parsed = stream.parsed
        assert parsed is not None
        assert parsed["verdict"] == "approved"
        assert stream.items == [{"file": "a.py"}]
        assert stream.metadata["verdict"] == "approved"

    def test_advance_when_complete_sets_summary_and_praise(self) -> None:
        stream = OllamaReviewStream()

        stream.advance(
            '{"verdict": "changes_requested", "reason": "r", "summary": "s", "suggestions": ["x"], "praise": ["y"]}',
            "complete",
        )

        parsed = stream.parsed
        assert parsed is not None
        assert parsed["reason"] == "r"
        assert stream.metadata["summary"] == "s"
        assert stream.metadata["suggestions"] == ["x"]
        assert stream.metadata["praise"] == ["y"]

    def test_advance_when_invalid_json_then_no_raise_keeps_parsed(self) -> None:
        stream = OllamaReviewStream()

        stream.advance("not json", "complete")

        assert stream.parsed is None
        assert stream.items is None

    def test_advance_when_not_complete_kind_then_only_content(self) -> None:
        stream = OllamaReviewStream()

        stream.advance("chunk", "tool_call")

        assert stream.content == "chunk"
        assert stream.kind == "tool_call"
        assert stream.parsed is None
