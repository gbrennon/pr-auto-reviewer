"""E2E review scenario registry — the single place to add test scenarios.

Each scenario is a dict you fill in to add a test case:

* ``platform`` — git host/platform (``forgejo``, ``github``).
* ``owner`` — owner username.
* ``repo`` — repository name.
* ``pr_id`` — pull request number.
* ``expected_items`` — number of review items the recorded replay must yield
  (optional; defaults to 0).

The ``review_output`` is auto-generated as
``file:reviews/{platform}_{owner}_{repo}_pr{pr_id}.md``.

* ``output_path`` — path to captured terminal output fixture (optional).

Adding a row here automatically expands every e2e test that parametrizes
over :data:`E2E_REVIEW_SCENARIOS` — no other code change needed.
"""

from __future__ import annotations

from typing import Required, TypedDict


class ReviewScenarioInput(TypedDict, total=False):
    """Input scenario — only required params."""

    platform: Required[str]
    owner: Required[str]
    repo: Required[str]
    pr_id: Required[int]
    expected_items: int
    output_path: str


class ReviewScenario(ReviewScenarioInput):
    """Normalized scenario — includes auto-generated review_output."""

    review_output: Required[str]


def _review_output(scenario: ReviewScenarioInput) -> str:
    """Generate review_output from required params."""
    return f"file:reviews/{scenario['platform']}_{scenario['owner']}_{scenario['repo']}_pr{scenario['pr_id']}.md"


def _normalize_scenario(scenario: ReviewScenarioInput) -> ReviewScenario:
    """Add auto-generated review_output and expected_items."""
    normalized: ReviewScenario = {
        "platform": scenario["platform"],
        "owner": scenario["owner"],
        "repo": scenario["repo"],
        "pr_id": scenario["pr_id"],
        "review_output": _review_output(scenario),
        "expected_items": scenario.get("expected_items", 0),
    }
    if "output_path" in scenario:
        normalized["output_path"] = scenario["output_path"]
    return normalized


def _get_normalized_scenarios() -> list[ReviewScenario]:
    return [_normalize_scenario(s) for s in E2E_REVIEW_SCENARIOS]


E2E_REVIEW_SCENARIOS: list[ReviewScenarioInput] = [
    {
        "platform": "github",
        "owner": "gbrennon",
        "repo": "ratatui",
        "pr_id": 1,
    },
    {
        "platform": "github",
        "owner": "gbrennon",
        "repo": "rataflow",
        "pr_id": 1,
        "expected_items": 1,
    }
]
