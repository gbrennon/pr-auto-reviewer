from ._helpers import *


class TestEnrichedFieldsThreading:
    """Factory carries remediation-context fields onto ReviewItem."""

    def test_remediation_fields_reach_review_item(self) -> None:
        factory = ReviewItemFactory()
        normalized = ReviewResponseParser.normalize_item_dict({
            "file": "src/a.py",
            "line": "10",
            "severity": "critical",
            "category": "security",
            "description": "SQL injection via string concatenation.",
            "current_code": "query = 'SELECT ' + user",
            "suggested_fix": "query = param(user)",
            "root_cause": "user input concatenated into SQL",
            "reproduction": "call build_query(\"' OR 1=1\")",
            "acceptance_criteria": "injection input returns no rows",
            "detection_method": "trace tainted input to the SQL sink",
        })

        items, _skips = factory.create([normalized], None)

        assert len(items) == 1
        item = items[0]
        assert item.root_cause == "user input concatenated into SQL"
        assert item.reproduction == "call build_query(\"' OR 1=1\")"
        assert item.acceptance_criteria == "injection input returns no rows"
        assert item.detection_method == "trace tainted input to the SQL sink"

    def test_absent_remediation_fields_default_empty(self) -> None:
        factory = ReviewItemFactory()
        normalized = ReviewResponseParser.normalize_item_dict({
            "file": "src/b.py",
            "line": "3",
            "severity": "minor",
            "category": "style",
            "description": "Line too long.",
            "current_code": "x = 1",
            "suggested_fix": "y = 2",
        })

        items, _skips = factory.create([normalized], None)

        item = items[0]
        assert item.root_cause == ""
        assert item.reproduction == ""
        assert item.acceptance_criteria == ""
        assert item.detection_method == ""
