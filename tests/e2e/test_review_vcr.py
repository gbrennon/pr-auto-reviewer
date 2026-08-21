import json
import re
from pathlib import Path

import pytest

from pr_auto_reviewer.application.ports.outbound.review_reader_port import ReviewReaderPort
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.presentation.composition_root import bootstrap
from tests.e2e.scenarios import ReviewScenario, _get_normalized_scenarios


def _cassette_name(scenario: ReviewScenario) -> str:
    """Generate cassette filename from scenario params."""
    return f"review_{scenario['platform']}_{scenario['owner']}_{scenario['repo']}_pr{scenario['pr_id']}"


@pytest.fixture
def vcr_config(scenario: ReviewScenario):
    return {
        "cassette_library_dir": "tests/e2e/cassettes/test_review_vcr",
        "match_on": ["method", "scheme", "host", "port", "path", "query"],
        "cassette_name": _cassette_name(scenario),
    }


def _read_review_body(
    review_output: str,
    pr_id: PullRequestId,
    review_reader: ReviewReaderPort,
) -> str | None:
    """Read the published review body from the output file or the platform."""
    if review_output.startswith("file:"):
        output_path = Path(review_output.removeprefix("file:"))
        if output_path.exists():
            return output_path.read_text(encoding="utf-8")
        return None
    return review_reader.get_latest_review(pr_id)


def _review_json(raw_body: str) -> dict:
    """Extract the JSON block from a published review body."""
    match = re.search(r"--- JSON ---\n\n(\{.*\})", raw_body, re.DOTALL)
    assert match is not None, "published review has no JSON block"
    return json.loads(match.group(1))


def _all_review_ids(payload: dict) -> list[str]:
    """Collect every item id from the published JSON payload."""
    ids: list[str] = []
    for section in ("items", "suggestions", "praise"):
        ids.extend(item.get("id", "") for item in payload.get(section, []))
    return ids


@pytest.mark.e2e
@pytest.mark.vcr
class TestReviewFlowVCR:
    @pytest.fixture
    def components(self, scenario, monkeypatch):
        monkeypatch.setenv("REVIEW_OUTPUT", scenario["review_output"])
        return bootstrap()

    @pytest.mark.parametrize(
        "scenario",
        _get_normalized_scenarios(),
        ids=lambda s: f"{s['platform']}:{s['owner']}/{s['repo']}#{s['pr_id']}",
    )
    def test_review_flow(self, components, scenario: dict) -> None:
        repo_spec = f"{scenario['platform']}:{scenario['owner']}/{scenario['repo']}"
        pr_id = PullRequestId(repository=repo_spec, number=scenario["pr_id"])

        review_argv = [
            "pr-auto-reviewer",
            "review",
            "--repo",
            repo_spec,
            "--pr",
            str(scenario["pr_id"]),
            "--force",
        ]
        exit_code = components.cli_runner.run(review_argv)
        assert exit_code == 0

        raw_body = _read_review_body(
            scenario["review_output"],
            pr_id,
            components.review_reader,
        )
        assert raw_body is not None

        payload = _review_json(raw_body)
        assert len(payload["items"]) == scenario["expected_items"]

        items = components.review_item_parser.parse(raw_body)
        assert len(items) == scenario["expected_items"]

        item_ids = _all_review_ids(payload)
        assert len(item_ids) == len(set(item_ids)), (
            f"duplicate ids in published review: {item_ids}"
        )
        assert all(item_ids), "published review contains empty item ids"
