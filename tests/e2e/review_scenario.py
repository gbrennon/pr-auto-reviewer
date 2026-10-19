from typing import Required

from tests.e2e.review_scenario_input import ReviewScenarioInput


class ReviewScenario(ReviewScenarioInput):
    """Normalized scenario with its generated review output."""

    review_output: Required[str]
