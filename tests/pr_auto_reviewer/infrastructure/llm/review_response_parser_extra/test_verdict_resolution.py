from ._helpers import *


class TestVerdictResolution:
    """Exercises verdict extraction and resolution."""

    def test_extract_verdict_md_when_heading_changes_then_changes_requested(self) -> None:
        assert (
            ReviewResponseParser().extract_verdict_md("## Verdict\nchanges_requested")
            == ReviewVerdict.CHANGES_REQUESTED
        )

    def test_extract_verdict_md_when_bold_approve_then_approved(self) -> None:
        assert (
            ReviewResponseParser().extract_verdict_md("**Verdict:** approve")
            == ReviewVerdict.APPROVED
        )

    def test_extract_verdict_md_when_bold_commented_then_raises(self) -> None:
        with pytest.raises(ReviewVerdictError):
            ReviewResponseParser().extract_verdict_md("**Verdict:** **commented**")

    def test_extract_verdict_md_when_plain_approve_then_approved(self) -> None:
        assert (
            ReviewResponseParser().extract_verdict_md("Verdict: approve")
            == ReviewVerdict.APPROVED
        )

    def test_extract_verdict_md_when_absent_then_raises(self) -> None:
        with pytest.raises(ReviewVerdictError):
            ReviewResponseParser().extract_verdict_md("nothing here")

    def test_resolve_verdict_when_request_changes_then_cr(self) -> None:
        assert (
            ReviewResponseParser()._resolve_verdict("request changes", [])
            == ReviewVerdict.CHANGES_REQUESTED
        )

    def test_resolve_verdict_when_explicit_value_then_parsed(self) -> None:
        assert (
            ReviewResponseParser()._resolve_verdict("approved", [])
            == ReviewVerdict.APPROVED
        )

    def test_resolve_verdict_when_missing_then_raises(self) -> None:
        with pytest.raises(ReviewVerdictError):
            ReviewResponseParser()._resolve_verdict(None, [])

    def test_resolve_verdict_when_commented_then_raises(self) -> None:
        with pytest.raises(ReviewVerdictError):
            ReviewResponseParser()._resolve_verdict("commented", [])

    def test_resolve_verdict_when_unknown_then_raises(self) -> None:
        with pytest.raises(ReviewVerdictError):
            ReviewResponseParser()._resolve_verdict("not-a-verdict", [])

    def test_resolve_reason_when_string_then_returned(self) -> None:
        assert ReviewResponseParser()._resolve_reason({"reason": "because"}) == "because"

    def test_resolve_reason_when_blank_then_raises(self) -> None:
        with pytest.raises(ReviewVerdictError):
            ReviewResponseParser()._resolve_reason({"reason": " "})

    def test_resolve_reason_when_alias_then_raises(self) -> None:
        with pytest.raises(ReviewVerdictError):
            ReviewResponseParser()._resolve_reason({"reasons": ["a", "b"]})

    def test_resolve_reason_when_missing_then_raises(self) -> None:
        with pytest.raises(ReviewVerdictError):
            ReviewResponseParser()._resolve_reason({})

