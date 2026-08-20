"""E2E review scenario registry — the single place to add test scenarios.

Each scenario is a dict you fill in to add a test case:

* ``platform`` — git host/platform (``forgejo``, ``github``).
* ``owner`` — owner username.
* ``repo`` — repository name.
* ``pr_id`` — pull request number.
* ``terminal_output`` — path to a captured terminal output file (optional).
  When the file exists, the captured-behavior e2e test parses its
  ``--- JSON ---`` block and asserts no default values. When missing, those
  tests skip and only the VCR record/replay test runs.

Adding a row here automatically expands every e2e test that parametrizes
over :data:`E2E_REVIEW_SCENARIOS` — no other code change needed.
"""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict

TERMINAL_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "terminal"


class ReviewScenario(TypedDict, total=False):
    """One fill-in e2e review scenario."""

    platform: str
    owner: str
    repo: str
    pr_id: int
    terminal_output: str


E2E_REVIEW_SCENARIOS: list[ReviewScenario] = [
    {
        "platform": "forgejo",
        "owner": "gbrennon",
        "repo": "pr-auto-reviewer",
        "pr_id": 146,
        # Capture a REVIEW_OUTPUT=terminal run, put it under tests/fixtures/terminal/
        # and set its path here to activate the terminal-output assertion:
        # "terminal_output": str(TERMINAL_ROOT / "forgejo_gbrennon_pr-auto-reviewer_146.txt"),
    },
    {
        "platform": "github",
        "owner": "gbrennon",
        "repo": "pr-auto-reviewer",
        "pr_id": 1,
    },
]


def scenario_repo_spec(scenario: ReviewScenario) -> str:
    """Return the repo spec used by the CLI, e.g. ``forgejo:gbrennon/pr-auto-reviewer``."""
    platform = scenario.get("platform", "")
    owner = scenario.get("owner", "")
    repo = scenario.get("repo", "")
    return f"{platform}:{owner}/{repo}"


def scenario_terminal_path(scenario: ReviewScenario) -> Path | None:
    """Return the captured terminal-output path for *scenario*, or None."""
    raw = scenario.get("terminal_output")
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.exists() else None