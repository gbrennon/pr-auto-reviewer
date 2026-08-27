from ._helpers import *


class TestReviewVerdictCoerce:
    """Tests for ReviewVerdict.coerce(value) -> ReviewVerdict | None."""

    def test_coerce_none_returns_none(self) -> None:
        assert ReviewVerdict.coerce(None) is None

    def test_coerce_existing_member_returns_itself(self) -> None:
        assert ReviewVerdict.coerce(ReviewVerdict.APPROVED) is ReviewVerdict.APPROVED

    def test_coerce_exact_value(self) -> None:
        assert ReviewVerdict.coerce("approved") is ReviewVerdict.APPROVED
        assert ReviewVerdict.coerce("changes_requested") is ReviewVerdict.CHANGES_REQUESTED
        assert ReviewVerdict.coerce("commented") is ReviewVerdict.COMMENTED

    def test_coerce_spaced_value(self) -> None:
        assert ReviewVerdict.coerce("changes requested") is ReviewVerdict.CHANGES_REQUESTED

    def test_coerce_whitespace_padded(self) -> None:
        assert ReviewVerdict.coerce("  APPROVED  ") is ReviewVerdict.APPROVED

    def test_coerce_blank_returns_none(self) -> None:
        assert ReviewVerdict.coerce("   ") is None

    def test_coerce_no_issues_phrase_approves(self) -> None:
        assert ReviewVerdict.coerce("no issues found") is ReviewVerdict.APPROVED
        assert ReviewVerdict.coerce("no_issues") is ReviewVerdict.APPROVED
        assert ReviewVerdict.coerce("no critical concerns") is ReviewVerdict.APPROVED

    def test_coerce_positive_token_approves(self) -> None:
        assert ReviewVerdict.coerce("looks clean") is ReviewVerdict.APPROVED
        assert ReviewVerdict.coerce("pass") is ReviewVerdict.APPROVED

    def test_coerce_negative_token_requests_changes(self) -> None:
        assert ReviewVerdict.coerce("critical problems") is ReviewVerdict.CHANGES_REQUESTED
        assert ReviewVerdict.coerce("needs work") is ReviewVerdict.CHANGES_REQUESTED

    def test_coerce_unknown_returns_none(self) -> None:
        assert ReviewVerdict.coerce("banana") is None

