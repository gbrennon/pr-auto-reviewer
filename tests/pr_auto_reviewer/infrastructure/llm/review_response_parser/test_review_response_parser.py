import json
import re

from ._helpers import *


class TestReviewResponseParser:
    """Strict review-envelope behavior of ReviewResponseParser."""

    @staticmethod
    def _empty_review(verdict: str = "approved") -> dict[str, object]:
        return {
            "verdict": verdict,
            "reason": "The supplied review is explicit.",
            "summary": "The review completed with explicit collections.",
            "items": [],
            "suggestions": [],
            "praise": [],
        }

    def test_parse_explicit_empty_review_returns_code_review(self) -> None:
        result = ReviewResponseParser().parse(
            json.dumps(self._empty_review()),
            "test-model",
        )

        assert isinstance(result, CodeReview)
        assert result.verdict == ReviewVerdict.APPROVED
        assert result.items == []
        assert result.suggestions == []
        assert result.praise == []
        assert result.model_used == "test-model"

    def test_parse_populated_review_preserves_explicit_values(self) -> None:
        payload = self._empty_review("changes_requested")
        payload["reason"] = "The item is blocking."
        payload["summary"] = "One blocking item remains."
        payload["issues"] = [{
            "file": "foo.py",
            "line": "3",
            "severity": "high",
            "type": "security",
            "description": "Input is not validated.",
            "current_code": "value = request.args['value']",
            "suggested_fix": "",
        }]
        payload.pop("items")
        payload["recommendations"] = [{
            "file": "foo.py",
            "description": "Add a regression test.",
            "suggested_code": "assert validate(value)",
        }]
        payload.pop("suggestions")
        payload["strengths"] = ["The change is well scoped."]
        payload.pop("praise")

        result = ReviewResponseParser().parse(json.dumps(payload), "m")

        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert result.items[0].severity.value == "major"
        assert result.items[0].category.value == "security"
        assert result.items[0].suggested_fix == ""
        assert result.suggestions[0].description == "Add a regression test."
        assert result.suggestions[0].suggested_fix == "assert validate(value)"
        assert result.praise[0].description == "The change is well scoped."

    def test_parse_accepts_legacy_verdict_spelling(self) -> None:
        payload = self._empty_review("request changes")

        result = ReviewResponseParser().parse(json.dumps(payload), "m")

        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED

    def test_parse_stop_token_and_code_block_are_supported(self) -> None:
        payload = json.dumps(self._empty_review())

        assert (
            ReviewResponseParser().parse(f"{payload}<|im_end|>", "m").verdict
            == ReviewVerdict.APPROVED
        )
        assert (
            ReviewResponseParser().parse(f"```json\n{payload}\n```", "m").verdict
            == ReviewVerdict.APPROVED
        )

    def test_parse_embedded_json_is_supported(self) -> None:
        payload = json.dumps(self._empty_review())

        result = ReviewResponseParser().parse(
            f"preamble {payload} trailing",
            "m",
        )

        assert result.verdict == ReviewVerdict.APPROVED

    def test_parse_rejects_missing_unknown_or_commented_verdict(self) -> None:
        for verdict in (None, "not-a-verdict", "commented"):
            payload = self._empty_review()
            if verdict is None:
                payload.pop("verdict")
            else:
                payload["verdict"] = verdict

            with pytest.raises(ReviewVerdictError):
                ReviewResponseParser().parse(json.dumps(payload), "m")

    def test_parse_rejects_blank_reason_or_summary(self) -> None:
        for field in ("reason", "summary"):
            payload = self._empty_review()
            payload[field] = " "

            with pytest.raises(ReviewVerdictError):
                ReviewResponseParser().parse(json.dumps(payload), "m")

    def test_parse_rejects_missing_or_ambiguous_findings_collection(self) -> None:
        missing = self._empty_review()
        missing.pop("items")
        both = self._empty_review()
        both["issues"] = []
        wrong_type = self._empty_review()
        wrong_type["items"] = {}

        for payload in (missing, both, wrong_type):
            with pytest.raises(ReviewVerdictError):
                ReviewResponseParser().parse(json.dumps(payload), "m")

    def test_parse_rejects_malformed_item_fields(self) -> None:
        for field_payload in (
            {"category": "bug", "description": "d"},
            {"severity": "major", "description": "d"},
            {"severity": "major", "category": "bug"},
            {
                "severity": "invalid",
                "category": "bug",
                "description": "d",
            },
            {
                "severity": "major",
                "category": "invalid",
                "description": "d",
            },
        ):
            payload = self._empty_review("changes_requested")
            payload["items"] = [field_payload]

            with pytest.raises(ReviewVerdictError):
                ReviewResponseParser().parse(json.dumps(payload), "m")

    def test_parse_rejects_wrong_collection_type_and_empty_entries(self) -> None:
        for field in ("suggestions", "praise"):
            wrong_type = self._empty_review()
            wrong_type[field] = {}
            empty_entry = self._empty_review()
            empty_entry[field] = [""]

            with pytest.raises(ReviewVerdictError):
                ReviewResponseParser().parse(json.dumps(wrong_type), "m")
            with pytest.raises(ReviewVerdictError):
                ReviewResponseParser().parse(json.dumps(empty_entry), "m")

    def test_parse_rejects_missing_suggestions_or_praise(self) -> None:
        for field in ("suggestions", "praise"):
            payload = self._empty_review()
            payload.pop(field)

            with pytest.raises(ReviewVerdictError):
                ReviewResponseParser().parse(json.dumps(payload), "m")

    def test_markdown_explicit_empty_review_is_supported(self) -> None:
        content = (
            "## Verdict\napproved\n\n"
            "**Reason:** No blocking issues were found.\n\n"
            "## Summary\nThe change is ready.\n\n"
            "## Items\nNone\n\n"
            "## Suggestions\nNone\n\n"
            "## Praise\nNone"
        )

        result = ReviewResponseParser().parse(content, "m")

        assert result.verdict == ReviewVerdict.APPROVED
        assert result.reason == "No blocking issues were found."
        assert result.summary == "The change is ready."
        assert result.items == []
        assert result.suggestions == []
        assert result.praise == []

    def test_markdown_missing_explicit_section_or_reason_is_rejected(self) -> None:
        missing_reason = (
            "## Verdict\napproved\n\n"
            "## Summary\nThe change is ready.\n\n"
            "## Items\nNone\n\n"
            "## Suggestions\nNone\n\n"
            "## Praise\nNone"
        )
        missing_section = (
            "## Verdict\napproved\n\n"
            "**Reason:** Explicit reason.\n\n"
            "## Summary\nThe change is ready.\n\n"
            "## Items\nNone"
        )

        for content in (missing_reason, missing_section):
            with pytest.raises(ReviewVerdictError):
                ReviewResponseParser().parse(content, "m")

    def test_markdown_structured_item_requires_valid_fields(self) -> None:
        content = (
            "## Verdict\nchanges_requested\n\n"
            "**Reason:** A blocking issue remains.\n\n"
            "## Summary\nThe item needs correction.\n\n"
            "## Items\n"
            "- [major] security (src/auth.py) Missing validation\n\n"
            "## Suggestions\nNone\n\n"
            "## Praise\nNone"
        )

        result = ReviewResponseParser().parse(content, "m")

        assert result.items[0].category.value == "security"
        assert result.items[0].description == "Missing validation"

    def test_parse_items_keeps_only_concrete_supplied_items(self) -> None:
        content = json.dumps({
            "items": [{
                "file": "a.py",
                "severity": "major",
                "category": "bug",
                "description": "A concrete issue.",
                "current_code": "old",
                "suggested_fix": "new",
            }],
        })

        result = ReviewResponseParser().parse_items(content)

        assert result[0]["file"] == "a.py"
        assert result[0]["description"] == "A concrete issue."

    def test_parse_item_observations_keep_explicit_description(self) -> None:
        content = json.dumps({
            "items": [{
                "file": "a.py",
                "severity": "minor",
                "category": "quality",
                "description": "An abstract concern.",
            }],
        })

        result = ReviewResponseParser().parse_item_observations(content)

        assert result == [{
            "file": "a.py",
            "line": "",
            "description": "An abstract concern.",
        }]

    def test_clean_response_and_outermost_json_helpers(self) -> None:
        parser = ReviewResponseParser()

        assert parser._clean_response('{"a": 1}<|im_end|>rest') == '{"a": 1}'
        outermost = parser.extract_outermost_json('{"a": {"b": 1}}')
        assert outermost == '{"a": {"b": 1}}'

    def test_suggestion_ids_are_six_character_hex_strings(self) -> None:
        payload = self._empty_review()
        payload["suggestions"] = [{"description": "Extract a helper."}]

        result = ReviewResponseParser().parse(json.dumps(payload), "m")

        assert re.fullmatch(r"[0-9a-f]{6}", result.suggestions[0].id)
