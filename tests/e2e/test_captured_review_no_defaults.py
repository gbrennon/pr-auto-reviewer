"""E2E behavior tests over captured reviews — no default values anywhere.

These tests are fill-in driven: a scenario (platform, owner, repo, pr_id,
terminal_output) is added in ``tests/e2e/scenarios.py`` and every test below
auto-expands.

* :class:`TestCapturedTerminalReviewCarriesNoDefaults` — when a scenario has
  a captured terminal output (``--- JSON ---`` block), assert the review
  payload carries no default/empty values.
* :class:`TestCapturedConversationsCarryRealBehavior` — conversation logs
  captured by ``scripts/capture_conversation_fixtures.py`` carry real
  verdicts and parsed findings.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.review_behavior_checks import ReviewPayloadBehaviorChecker
from tests.e2e.scenarios import (
    E2E_REVIEW_SCENARIOS,
    ReviewScenario,
    scenario_terminal_path,
)

FIXTURES_ROOT = Path(__file__).resolve().parents[2] / "fixtures" / "conversations"


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
                "No terminal_output set for scenario — add a captured "
                "REVIEW_OUTPUT=terminal file in tests/fixtures/terminal/ and "
                "reference it in tests/e2e/scenarios.py"
            )
        text = terminal_path.read_text(encoding="utf-8", errors="replace")
        payload = _terminal_payload(text)
        assert payload is not None, (
            f"{terminal_path} has no '--- JSON ---' review block"
        )
        violations = ReviewPayloadBehaviorChecker().violations(payload)
        assert not violations, "\n".join(violations)


def _captured_case_ids() -> list[str]:
    """Auto-discover phase fixtures written by ``capture_conversation_fixtures``."""
    manifest_path = FIXTURES_ROOT / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        return [entry["case_id"] for entry in manifest]
    if FIXTURES_ROOT.exists():
        return [
            str(p.relative_to(FIXTURES_ROOT)).removesuffix(".json")
            for p in FIXTURES_ROOT.rglob("*.json")
            if "manifest" not in p.name and "final_review" not in p.name
        ]
    return []


@pytest.mark.e2e
class TestCapturedConversationsCarryRealBehavior:
    """Captured phase conversations show real verdicts and parsed findings."""

    @pytest.mark.parametrize("case_id", _captured_case_ids())
    def test_phase_log_has_real_verdict(self, case_id: str) -> None:
        path = FIXTURES_ROOT / f"{case_id}.json"
        if not path.exists():
            pytest.skip("run capture_conversation_fixtures first")
        fixture = json.loads(path.read_text(encoding="utf-8"))
        verdict = str(fixture.get("llm_verdict", "")).strip().lower()
        assert verdict, "fixture has no llm_verdict"
        assert verdict not in ("unknown", "none", "no issues found across all review phases")
        assert fixture.get("turns", 0) >= 1
        assert fixture.get("model", "").strip(), "fixture model is empty"

        answers = [
            m.get("json")
            for m in fixture.get("messages", [])
            if m.get("direction") == "received"
            and m.get("kind") == "answer"
            and isinstance(m.get("json"), dict)
        ]
        final_answer = answers[-1] if answers else None
        assert final_answer is not None, "no parsed final answer in fixture"
        if "items" in final_answer:
            assert isinstance(final_answer["items"], list)