"""E2E review scenario registry — the single place to add test scenarios.

Each scenario is a dict you fill in to add a test case:

* ``platform`` — git host/platform (``forgejo``, ``github``).
* ``owner`` — owner username.
* ``repo`` — repository name.
* ``pr_id`` — pull request number.
* ``review_output`` — the value for ``REVIEW_OUTPUT`` (default ``"terminal"``).
  Accepts anything the app understands: ``terminal``, ``file:<path>``, or a
  platform name (e.g. ``forgejo``) to publish a real review.
* ``output_path`` — optional captured-output file path (``tests/fixtures/terminal/``).
  When set, the captured-behavior e2e test reads its ``--- JSON ---`` block
  and asserts no default values.
* ``terminal_output`` — retained alias for ``output_path`` (optional).

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
    review_output: str
    output_path: str
    terminal_output: str


DEFAULT_REVIEW_OUTPUT = "terminal"


E2E_REVIEW_SCENARIOS: list[ReviewScenario] = [
    {
        "platform": "forgejo",
        "owner": "gbrennon",
        "repo": "pr-auto-reviewer",
        "pr_id": 146,
        "review_output": "terminal",
        # Capture a REVIEW_OUTPUT=terminal run into tests/fixtures/terminal/
        # and set its path here to activate the no-defaults assertion:
        # "output_path": str(TERMINAL_ROOT / "forgejo_gbrennon_pr-auto-reviewer_146.txt"),
    },
    {
        "platform": "github",
        "owner": "gbrennon",
        "repo": "pr-auto-reviewer",
        "pr_id": 1,
        "review_output": "terminal",
    },
    {
        "platform": "forgejo",
        "owner": "gbrennon",
        "repo": "pr-auto-reviewer",
        "pr_id": 146,
        "review_output": "file:reviews/forgejo_146.md",
    },
]


def scenario_repo_spec(scenario: ReviewScenario) -> str:
    """Return the repo spec used by the CLI, e.g. ``forgejo:gbrennon/pr-auto-reviewer``."""
    platform = scenario.get("platform", "")
    owner = scenario.get("owner", "")
    repo = scenario.get("repo", "")
    return f"{platform}:{owner}/{repo}"


def scenario_review_output(scenario: ReviewScenario) -> str:
    """Return the ``REVIEW_OUTPUT`` value for *scenario* (default ``terminal``)."""
    return scenario.get("review_output") or DEFAULT_REVIEW_OUTPUT


def scenario_terminal_path(scenario: ReviewScenario) -> Path | None:
    """Return the captured terminal-output path for *scenario*, or None.

    Honors ``output_path`` first, then the legacy ``terminal_output`` alias.
    """
    raw = scenario.get("output_path") or scenario.get("terminal_output")
    if not raw:
        return None
    path = Path(raw).expanduser()
    return path if path.exists() else None