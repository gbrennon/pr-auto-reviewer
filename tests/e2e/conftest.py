import pytest

from tests.e2e.scenarios import (
    E2E_REVIEW_SCENARIOS,
    ReviewScenario,
    _normalize_scenario,
)


@pytest.fixture(params=E2E_REVIEW_SCENARIOS)
def review_scenario(request) -> ReviewScenario:
    """Parametrize over the raw defined scenarios, normalized for tests."""
    return _normalize_scenario(request.param)