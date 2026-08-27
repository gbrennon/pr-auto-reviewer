from ._helpers import *


class TestSubAgentGrade:
    """The advisor's S/B/D/F grade vocabulary."""

    def test_members_map_to_documented_phrases(self) -> None:
        assert SubAgentGrade.IMPRESSIVE.value == "impressive"
        assert SubAgentGrade.OKOK.value == "okok"
        assert SubAgentGrade.WHATEVER.value == "whatever"
        assert SubAgentGrade.DONT_DO_THIS.value == "don't do this!"

    def test_from_phrase_matches_each_grade(self) -> None:
        assert SubAgentGrade.from_phrase("impressive") is SubAgentGrade.IMPRESSIVE
        assert SubAgentGrade.from_phrase("okok") is SubAgentGrade.OKOK
        assert SubAgentGrade.from_phrase("whatever") is SubAgentGrade.WHATEVER
        assert SubAgentGrade.from_phrase("don't do this!") is (
            SubAgentGrade.DONT_DO_THIS
        )

    def test_from_phrase_unknown_falls_back_to_okok(self) -> None:
        assert SubAgentGrade.from_phrase("excellent") is SubAgentGrade.OKOK
        assert SubAgentGrade.from_phrase("") is SubAgentGrade.OKOK

    def test_only_f_blocks(self) -> None:
        assert SubAgentGrade.IMPRESSIVE.blocks is False
        assert SubAgentGrade.OKOK.blocks is False
        assert SubAgentGrade.WHATEVER.blocks is False
        assert SubAgentGrade.DONT_DO_THIS.blocks is True

