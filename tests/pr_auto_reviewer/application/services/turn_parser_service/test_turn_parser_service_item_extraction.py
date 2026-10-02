from ._helpers import *


class TestTurnParserServiceItemExtraction:
    """TurnParserService must pass normalized item dicts into raw_items."""

    def test_verdict_branch_normalizes_issue_items(self) -> None:
        parser = TurnParserService(ReviewResponseParser())
        result = parser.execute(ParseReviewTurnCommand(content=json.dumps({
            "verdict": "Needs Improvement",
            "reason": "lacks error handling",
            "items": [
                {"file": "src/a.py", "issue": "No error handling.",
                 "severity": "High"},
            ],
        })))
        assert result.kind is TurnKind.VERDICT
        assert result.raw_items is not None
        assert len(result.raw_items) == 1
        assert result.raw_items[0]["description"] == "No error handling."
        assert result.raw_items[0]["severity"] == "major"

    def test_verdict_branch_keeps_string_items_out_of_raw_items(self) -> None:
        parser = TurnParserService(ReviewResponseParser())
        result = parser.execute(ParseReviewTurnCommand(content=json.dumps({
            "verdict": "approved",
            "items": ["Review multi_phase_orchestrator.py"],
        })))
        assert result.kind is TurnKind.VERDICT
        assert result.raw_items == []
        assert result.metadata is not None
        assert result.metadata["suggestions"] != []

    def test_positive_verdict_coerces_to_approved(self) -> None:
        parser = TurnParserService(ReviewResponseParser())
        result = parser.execute(ParseReviewTurnCommand(content=json.dumps({
            "verdict": "Positive",
            "reason": "codebase is clean",
            "items": [],
        })))
        assert result.metadata is not None
        assert result.metadata["verdict"] == "approved"

    def test_no_issues_found_coerces_to_approved(self) -> None:
        parser = TurnParserService(ReviewResponseParser())
        result = parser.execute(ParseReviewTurnCommand(content=json.dumps({
            "verdict": "no_issues_found",
            "items": [],
        })))
        assert result.metadata is not None
        assert result.metadata["verdict"] == "approved"

    def test_prose_findings_without_verdict_derive_changes_requested(self) -> None:
        content = (
            "#### 1. Hardcoded timeout in `src/a.py` [major]\n"
            "The module hardcodes a timeout instead of reading config.\n"
            "```python\n"
            "TIMEOUT = 30\n"
            "```\n"
            "Suggested fix:\n"
            "```python\n"
            "TIMEOUT = settings.timeout\n"
            "```\n"
        )
        parser = TurnParserService(ReviewResponseParser())
        result = parser.execute(ParseReviewTurnCommand(content=content))

        assert result.kind is TurnKind.VERDICT
        assert result.metadata is not None
        assert result.metadata["verdict"] == "changes_requested"
        assert result.metadata["reason"] != ""
        assert result.metadata["summary"] != ""

    def test_prose_minor_findings_without_verdict_derive_approved(self) -> None:
        content = (
            "#### 1. Trailing whitespace in `src/a.py` [minor]\n"
            "```python\n"
            "x = 1 \n"
            "```\n"
            "Suggested fix:\n"
            "```python\n"
            "x = 1\n"
            "```\n"
        )
        parser = TurnParserService(ReviewResponseParser())
        result = parser.execute(ParseReviewTurnCommand(content=content))

        assert result.kind is TurnKind.VERDICT
        assert result.metadata is not None
        assert result.metadata["verdict"] == "approved"
        assert result.metadata["reason"] != ""
