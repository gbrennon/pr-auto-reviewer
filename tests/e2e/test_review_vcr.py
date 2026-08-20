"""Record-and-replay E2E tests using vcrpy — real captures, offline replay.

vcrpy with ``record_mode="once"`` is self-managing — no flags:

* First run (no cassette): vcrpy **automatically records** the real HTTP
  interactions (Forgejo/Codeberg + Ollama) into ``tests/e2e/cassettes/``.
* Later runs (cassette exists): vcrpy **replays** the recorded interaction,
  so no request reaches ollama/codeberg/github.

This is the Ruby-VCR pattern: the first decorated call exercises the real
services once; every later call relies on the recorded fixture.

Scenarios come from :data:`tests.e2e.scenarios.E2E_REVIEW_SCENARIOS` — add a
row there (platform, owner, repo, pr_id) to add a capture/replay case:

    forgejo:gbrennon/pr-auto-reviewer #146  ->  review_forgejo_yaml cassette

The in-process driver mirrors exactly the CLI the user runs:

    REVIEW_OUTPUT=terminal uv run pr-auto-reviewer review --force \\
        -r forgejo:gbrennon/pr-auto-reviewer -p 146
"""

from __future__ import annotations

import contextlib
import io
import json
import os
from typing import Any

import pytest
import vcr

from scripts.review_behavior_checks import ReviewPayloadBehaviorChecker
from tests.e2e.scenarios import (
    E2E_REVIEW_SCENARIOS,
    ReviewScenario,
    scenario_repo_spec,
)

CASSETTES_DIR = "tests/e2e/cassettes"


def _cassette_name(platform: str, owner: str, repo: str, pr_id: int) -> str:
    """Return the cassette filename for a scenario."""
    safe = f"{platform}_{owner}_{repo}_pr{pr_id}".replace("/", "_")
    return f"review_{safe}.yaml"


def _vcr_for(cassette_name: str) -> vcr.VCR:
    """Return a VCR instance that auto-records when *cassette_name* is missing.

    ``record_mode="once"``: records only when the cassette does not exist;
    thereafter replays, never touching the network.
    """
    return vcr.VCR(
        serializer="yaml",
        cassette_library_dir=CASSETTES_DIR,
        record_mode="once",
        match_on=["uri", "method"],
        filter_headers=["Authorization", "authorization", "token"],
        filter_query_parameters=["token", "access_token"],
    )


def _run_cli_like(repo_spec: str, pr_number: int) -> str:
    """Run the review entrypoint in-process exactly like the CLI, returning stdout.

    Mirrors ``REVIEW_OUTPUT=terminal uv run pr-auto-reviewer review --force
    -r <repo_spec> -p <pr>`` so vcrpy can intercept the HTTP calls.
    """
    from pr_auto_reviewer.presentation.composition_root import bootstrap

    os.environ["REVIEW_OUTPUT"] = "terminal"
    argv = [
        "pr-auto-reviewer",
        "review",
        "--force",
        "--repo",
        repo_spec,
        "--pr",
        str(pr_number),
    ]
    components = bootstrap()
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        exit_code = components.cli_runner.run(argv)
    output = buffer.getvalue()
    os.environ.pop("REVIEW_OUTPUT", None)
    assert exit_code == 0, f"review exited {exit_code}\n=====\n{output[-2000:]}"
    return output


def _terminal_review_payload(output: str) -> dict[str, Any]:
    """Extract the ``--- JSON ---`` review payload from terminal output."""
    marker = "--- JSON ---"
    if marker not in output:
        pytest.fail(f"terminal output has no JSON section:\n{output[-1500:]}")
    section = output.split(marker, 1)[1]
    section = section.split("\n" + "=" * 30, 1)[0].strip()
    return json.loads(section)


@pytest.mark.e2e
class TestReviewHttpRecording:
    """Auto-record once, then replay the review HTTP interaction offline."""

    @pytest.mark.parametrize(
        "scenario",
        E2E_REVIEW_SCENARIOS,
        ids=lambda s: f"{s['platform']}:{s['owner']}/{s['repo']}#{s['pr_id']}",
    )
    def test_review_flow_captured_or_replayed(self, scenario: ReviewScenario) -> None:
        repo_spec = scenario_repo_spec(scenario)
        pr_number = int(scenario["pr_id"])
        cassette = _cassette_name(
            scenario["platform"], scenario["owner"], scenario["repo"], pr_number,
        )
        vcr_instance = _vcr_for(cassette)

        with vcr_instance.use_cassette(cassette):
            output = _run_cli_like(repo_spec, pr_number)
            review_payload = _terminal_review_payload(output)

        violations = ReviewPayloadBehaviorChecker().violations(review_payload)
        assert not violations, "\n".join(violations)