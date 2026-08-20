"""E2E behavior tests over captured reviews — no default values anywhere.

These tests are fill-in driven: a scenario (platform, owner, repo, pr_id,
terminal_output) is added in ``tests/e2e/scenarios.py`` and every test below
auto-expands. vcrpy owns the HTTP capture (see ``test_review_vcr.py``); here
we only assert *behavior* of captured terminal output.

When a scenario has ``terminal_output`` set to a captured
``REVIEW_OUTPUT=terminal`` run, the ``--- JSON ---`` block in that file must
carry no default/empty values — verdict, reason, summary, and every item
field must be filled from the real review, never a default.
"""

from __future__ import annotations

import json

import pytest

from scripts.review_behavior_checks import ReviewPayloadBehaviorChecker
from tests.e2e.scenarios import (
    E2E_REVIEW_SCENARIOS,
    ReviewScenario,
    scenario_terminal_path,
)


def _terminal_payload(text: str) -> dict | None:
    """Extract the ``--- JSON ---`` review payload from *text*, or None."""
    marker = "--- JSON ---"
    if marker not in text:
        return None
    section = text.split(marker, 1)[1]
    section = section.split("\n" + "=" * 30, 1)[0].strip()
    try:
        payload = json.loads(section)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


@pytest.mark.e2e
class TestCapturedTerminalReviewCarriesNoValues:
    """A captured terminal review JSON carries no default/empty values."""

    @pytest.mark.parametrize(
        "scenario",
        E2E_REVIEW_SCENARIOS,
        ids=lambda s: f"{s['platform']}:{s['owner']}/{s['repo']}#{s['pr_id']}",
    )
    def test_terminal_review_no_defaults(self, scenario: ReviewScenario) -> None:
        terminal_path = scenario_terminal_path(scenario)
        if terminal_path is None:
            pytest.skip(
                "No terminal_output set for scenario — put a captured "
                "REVIEW_OUTPUT=terminal file under tests/fixtures/terminal/ "
                "and reference it in tests/e2e/scenarios.py"
            )
        text = terminal_path.read_text(encoding="utf-8", errors="replace")
        payload = _terminal_payload(text)
        assert payload is not None, (
            f"{terminal_path} has no '--- JSON ---' review block"
        )
        violations = ReviewPayloadBehaviorChecker().violations(payload)
        assert not violations, "\n".join(violations)