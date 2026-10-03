"""Round-trip tests for the enriched ReviewItem persistence codec."""

from __future__ import annotations

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.infrastructure.persistence import json_file_pr_repository as repo


class TestEnrichedItemRoundtrip:
    def test_enriched_fields_survive_roundtrip(self) -> None:
        item = ReviewItem(
            severity="major",
            category="correctness",
            file_path="src/a.py",
            description="off-by-one",
            root_cause="loop uses <= instead of <",
            reproduction="run parse([1,2,3]) -> IndexError",
            acceptance_criteria="parse([1,2,3]) returns 3 items, no error",
            detection_method="boundary analysis of the loop index",
        )
        restored = repo.ReviewItemCodec.deserialize(
            repo.ReviewItemCodec.serialize(item)
        )
        assert restored.root_cause == item.root_cause
        assert restored.reproduction == item.reproduction
        assert restored.acceptance_criteria == item.acceptance_criteria
        assert restored.detection_method == item.detection_method

    def test_legacy_payload_without_new_fields_loads_empty(self) -> None:
        legacy = {
            "severity": "minor",
            "category": "general",
            "file_path": "src/a.py",
            "description": "x",
            "status": "open",
        }
        restored = repo.ReviewItemCodec.deserialize(legacy)
        assert restored.root_cause == ""
        assert restored.detection_method == ""
