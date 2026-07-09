"""Tests for RateLimitSnapshot using captured fixtures."""

from pr_auto_reviewer.infrastructure.client.rate_limit_snapshot import RateLimitSnapshot
from tests.fixtures.rate_limit_fixtures import RateLimitFixtures as F


class TestRateLimitSnapshot:
    def test_defaults(self):
        s = RateLimitSnapshot()
        assert s.limit == 0
        assert s.remaining == 0
        assert s.used == 0
        assert s.reset == 0
        assert s.resource == ""

    def test_from_full_headers(self):
        s = RateLimitSnapshot.from_response_headers(F.full_headers)
        assert s.limit == 5000
        assert s.remaining == 4990
        assert s.used == 10
        assert s.resource == "core"

    def test_from_minimal_headers(self):
        s = RateLimitSnapshot.from_response_headers(F.minimal_headers)
        assert s.limit == 5000
        assert s.remaining == 2500
        assert s.used == 0

    def test_from_empty_headers(self):
        s = RateLimitSnapshot.from_response_headers(F.empty_headers)
        assert s.limit == 0
        assert s.remaining == 0

    def test_exhausted_when_remaining_zero(self):
        s = RateLimitSnapshot.from_response_headers(F.exhausted_headers)
        assert s.exhausted() is True

    def test_not_exhausted_when_remaining_positive(self):
        s = RateLimitSnapshot.from_response_headers(F.full_headers)
        assert s.exhausted() is False

    def test_not_exhausted_when_limit_zero(self):
        s = RateLimitSnapshot(limit=0, remaining=0)
        assert s.exhausted() is False

    def test_reset_seconds_from_now_future(self):
        import time

        future = int(time.time()) + 100
        s = RateLimitSnapshot(reset=future)
        assert 90 <= s.reset_seconds_from_now() <= 100

    def test_reset_seconds_from_now_past(self):
        import time

        past = int(time.time()) - 100
        s = RateLimitSnapshot(reset=past)
        assert s.reset_seconds_from_now() == 0

    def test_reset_seconds_from_now_zero(self):
        s = RateLimitSnapshot(reset=0)
        assert s.reset_seconds_from_now() == 0

    def test_summary_includes_remaining(self):
        s = RateLimitSnapshot.from_response_headers(F.full_headers)
        summary = s.summary()
        assert "remaining=4990/5000" in summary

    def test_to_dict_roundtrip(self):
        s = RateLimitSnapshot.from_response_headers(F.full_headers)
        d = s.to_dict()
        assert d["limit"] == 5000
        assert d["remaining"] == 4990
