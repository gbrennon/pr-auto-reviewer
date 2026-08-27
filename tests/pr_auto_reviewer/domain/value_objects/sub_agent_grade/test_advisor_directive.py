from ._helpers import *


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
