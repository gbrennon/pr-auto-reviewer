"""Regression tests: review pipeline must never emit empty JSON fields.

Covers the fixes that made the terminal review output carry real content:
LLM item dicts with ``issue``/``severity`` keys survive normalization and
the factory; suggestions are grounded against repo files; the terminal
JSON omits empty nested fields; and the ``commented`` verdict is the
failure marker, not a silent default.
"""

from pr_auto_reviewer.domain.services.review_item_factory import ReviewItemFactory
from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)


class TestFactoryKeepsUnverifiedItems:
    """Factory must not drop items solely for missing code snippets."""

    def test_item_without_code_survives_with_evidence(self, tmp_path) -> None:
        repo = tmp_path / "repo"
        target = repo / "src" / "multi_phase_review_orchestrator.py"
        target.parent.mkdir(parents=True)
        target.write_text(
            "def run_phases(self, plan):\n"
            "    for phase in plan.phases:\n"
            "        process(phase)\n"
        )
        factory = ReviewItemFactory()
        normalized = ReviewResponseParser._normalize_item_dict({
            "file": "src/multi_phase_review_orchestrator.py",
            "issue": "Missing validation for phase dependencies.",
            "severity": "high",
        })
        items, _skips = factory.create(
            [normalized],
            repo,
            ["src/multi_phase_review_orchestrator.py"],
        )
        assert len(items) == 1
        assert items[0].description == (
            "Missing validation for phase dependencies."
        )
        assert items[0].suggested_fix != ""
        assert items[0].current_code != ""