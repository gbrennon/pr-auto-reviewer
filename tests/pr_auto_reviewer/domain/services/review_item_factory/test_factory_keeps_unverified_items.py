from ._helpers import *


class TestFactoryKeepsUnverifiedItems:
    """Factory must not drop items solely for missing code snippets."""

    def test_item_without_code_survives_with_evidence(self, tmp_path) -> None:
        repo = tmp_path / "repo"
        target = repo / "src" / "multi_phase_review_orchestrator_service.py"
        target.parent.mkdir(parents=True)
        target.write_text(
            "def run_phases(self, plan):\n"
            "    for phase in plan.phases:\n"
            "        process(phase)\n"
        )
        factory = ReviewItemFactory()
        normalized = ReviewResponseParser.normalize_item_dict({
            "file": "src/multi_phase_review_orchestrator_service.py",
            "issue": "Missing validation for phase dependencies.",
            "severity": "high",
        })
        items, _skips = factory.create(
            [normalized],
            repo,
            ["src/multi_phase_review_orchestrator_service.py"],
        )
        assert len(items) == 1
        assert items[0].description == (
            "Missing validation for phase dependencies."
        )
        assert items[0].suggested_fix != ""
        assert items[0].current_code != ""

