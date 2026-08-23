"""Tests for SubAgentGrade and AdvisorDirective."""

from __future__ import annotations

from pr_auto_reviewer.domain.value_objects.advisor_directive import (
    AdvisorDirective,
)
from pr_auto_reviewer.domain.value_objects.sub_agent_grade import (
    SubAgentGrade,
)


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


class TestAdvisorDirective:
    """The advisor's grade plus corrective materials."""

    def test_blocks_output_mirrors_grade(self) -> None:
        assert AdvisorDirective(
            grade=SubAgentGrade.DONT_DO_THIS,
            feedback="don't do this!",
            improved_prompt="redo it",
        ).blocks_output is True
        assert AdvisorDirective(
            grade=SubAgentGrade.OKOK
        ).blocks_output is False

    def test_defaults_are_empty(self) -> None:
        directive = AdvisorDirective(grade=SubAgentGrade.IMPRESSIVE)
        assert directive.feedback == ""
        assert directive.improved_prompt == ""