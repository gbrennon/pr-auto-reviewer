import json
import re
from pathlib import Path

import pytest

from pr_auto_reviewer.application.ports.outbound.review_reader_port import (
    ReviewReaderPort,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.presentation.composition_root import bootstrap
from pr_auto_reviewer.presentation.polling_daemon import (
    PollingDaemon,
    PollingDaemonConfig,
)
from tests.e2e.scenario_pr_lister import ScenarioPrLister
from tests.e2e.scenario_repo_lister import ScenarioRepoLister
from tests.e2e.scenarios import ReviewScenario, get_normalized_scenarios
from tests.fakes.fake_notifier import FakeNotifier


def _cassette_name(scenario: ReviewScenario) -> str:
    """Generate cassette filename from scenario params."""
    return f"review_{scenario['platform']}_{scenario['owner']}_{scenario['repo']}_pr{scenario['pr_id']}"


@pytest.fixture
def default_cassette_name(request: pytest.FixtureRequest) -> str:
    cassette_name = request.node.name.replace(
        "test_daemon_review_flow_notifies_success",
        "test_review_flow",
    )
    for character in r'<>?%*:|"/\\':
        cassette_name = cassette_name.replace(character, "-")
    return f"TestReviewFlowVCR.{cassette_name}"

@pytest.fixture
def vcr_config(scenario: ReviewScenario):
    return {
        "cassette_library_dir": "tests/e2e/cassettes/review_vcr",
        "match_on": ["method", "scheme", "host", "port", "path", "query"],
        "filter_headers": ["authorization"],
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
    def notifier(self) -> FakeNotifier:
        return FakeNotifier()

    @pytest.fixture
    def components(
        self, scenario, monkeypatch, notifier: FakeNotifier, tmp_path: Path,
    ):
        """Bootstrap against temporary artifact homes.

        A minimal synthetic config keeps machine settings (such as
        ``DEBUG``, which flips process-wide logging) from leaking into
        the test run. Cassettes carry no preflight ``GET /user``
        recordings, so both token roles start pre-verified, mirroring
        the cached state present when they were captured.
        """
        xdg_cache = tmp_path / "xdg-cache"
        monkeypatch.setenv("XDG_CACHE_HOME", str(xdg_cache))
        monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path / "xdg-state"))
        xdg_config = tmp_path / "xdg-config"
        monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))
        config_file = xdg_config / "pr-auto-reviewer" / "config"
        config_file.parent.mkdir(parents=True, exist_ok=True)
        config_file.write_text("\n".join([
            f"PLATFORM_MODE={scenario['platform']}",
            "GITHUB_API_URL=https://api.github.com",
            "GITHUB_OWNER_TOKEN=e2e-owner-token",
            "GITHUB_REVIEWER_TOKEN=e2e-reviewer-token",
            "GITHUB_REVIEWER_USERNAME=e2e-reviewer",
            "LLM_HOST=http://localhost:11434",
            "LLM_MODEL=code-review:latest",
        ]) + "\n")
        token_store = xdg_cache / "pr-auto-reviewer" / "verified-tokens.json"
        token_store.parent.mkdir(parents=True, exist_ok=True)
        token_store.write_text(json.dumps([
            [scenario["owner"], "owner"],
            [scenario["owner"], "reviewer"],
        ]))
        monkeypatch.setenv("LLM_HOST", "http://localhost:11434")
        monkeypatch.setenv("LLM_MODEL", "code-review:latest")
        monkeypatch.setenv("REVIEW_OUTPUT", scenario["review_output"])
        return bootstrap(notifier=notifier)

    @pytest.mark.parametrize(
        "scenario",
        get_normalized_scenarios(),
        ids=lambda s: f"{s['platform']}:{s['owner']}/{s['repo']}#{s['pr_id']}",
    )
    def test_review_flow(
        self, components, scenario: dict, notifier: FakeNotifier,
    ) -> None:
        repo_spec = f"{scenario['platform']}:{scenario['owner']}/{scenario['repo']}"
        pr_id = PullRequestId(repository=repo_spec, number=scenario["pr_id"])
        expected_repository = (
            f"{scenario['owner']}/{scenario['repo']}"
        )

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
        assert notifier.errors == []
        assert len(notifier.successes) == 1
        notification_context, notification_detail = notifier.successes[0]
        assert notification_context.startswith(
            f"Review complete for {expected_repository} ("
        )
        assert notification_context.endswith(")")
        assert notification_detail == f"PR #{scenario['pr_id']}"

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

    @pytest.mark.parametrize(
        "scenario",
        get_normalized_scenarios(),
        ids=lambda s: f"{s['platform']}:{s['owner']}/{s['repo']}#{s['pr_id']}",
    )
    def test_daemon_review_flow_notifies_success(
        self, components, scenario: ReviewScenario, notifier: FakeNotifier,
    ) -> None:
        repository = (
            f"{scenario['platform']}:{scenario['owner']}/{scenario['repo']}"
        )
        expected_repository = (
            f"{scenario['owner']}/{scenario['repo']}"
        )
        daemon = PollingDaemon(
            config=PollingDaemonConfig(
                poll_interval_seconds=1,
                repos_filter=repository,
                repos_allow_list=(),
                run_once=True,
                force_pr=scenario["pr_id"],
            ),
            repo_lister=ScenarioRepoLister(repository),
            pr_lister=ScenarioPrLister(components.pr_lister, scenario["pr_id"]),
            review_service=components.review_service,
            notifier=notifier,
        )

        daemon.start()

        assert notifier.errors == []
        assert len(notifier.successes) == 1
        notification_context, notification_detail = notifier.successes[0]
        assert notification_context.startswith(
            f"Review complete for {expected_repository} ("
        )
        assert notification_context.endswith(")")
        assert notification_detail == f"PR #{scenario['pr_id']}"
