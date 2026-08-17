import pytest

from pr_auto_reviewer.domain import ReviewVerdict


class TestReviewVerdict:
    """Tests for ReviewVerdict enum."""

    def test_members_exist(self) -> None:
        assert ReviewVerdict.APPROVED == "approved"
        assert ReviewVerdict.CHANGES_REQUESTED == "changes_requested"
        assert ReviewVerdict.COMMENTED == "commented"

    def test_three_states_only(self) -> None:
        members = list(ReviewVerdict)
        assert len(members) == 3
        names = {m.name for m in members}
        assert names == {"APPROVED", "CHANGES_REQUESTED", "COMMENTED"}

    def test_equality_same_verdict(self) -> None:
        assert ReviewVerdict.APPROVED == ReviewVerdict.APPROVED
        assert ReviewVerdict.CHANGES_REQUESTED == ReviewVerdict.CHANGES_REQUESTED

    def test_equality_different_verdict(self) -> None:
        assert ReviewVerdict.APPROVED != ReviewVerdict.CHANGES_REQUESTED
        assert ReviewVerdict.APPROVED != ReviewVerdict.COMMENTED

    def test_str_representation(self) -> None:
        assert str(ReviewVerdict.APPROVED) == "approved"
        assert str(ReviewVerdict.CHANGES_REQUESTED) == "changes_requested"
        assert str(ReviewVerdict.COMMENTED) == "commented"

    def test_hash(self) -> None:
        assert hash(ReviewVerdict.APPROVED) == hash(ReviewVerdict.APPROVED)
        s = {ReviewVerdict.APPROVED, ReviewVerdict.COMMENTED}
        assert ReviewVerdict.APPROVED in s

    def test_from_string(self) -> None:
        assert ReviewVerdict("approved") == ReviewVerdict.APPROVED
        assert ReviewVerdict("changes_requested") == ReviewVerdict.CHANGES_REQUESTED
        assert ReviewVerdict("commented") == ReviewVerdict.COMMENTED

    def test_invalid_value_raises(self) -> None:
        with pytest.raises(ValueError):
            ReviewVerdict("invalid")

    def test_string_comparison(self) -> None:
        assert ReviewVerdict.APPROVED == "approved"
        assert ReviewVerdict.APPROVED != "changes_requested"


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
