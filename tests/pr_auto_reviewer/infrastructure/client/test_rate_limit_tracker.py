"""Tests for RateLimitTracker using captured fixtures."""

import io
from pathlib import Path

from pr_auto_reviewer.infrastructure.client.rate_limit_snapshot import RateLimitSnapshot
from pr_auto_reviewer.infrastructure.client.rate_limit_tracker import RateLimitTracker
from tests.fixtures.rate_limit_fixtures import RateLimitFixtures as F


class TestRateLimitTracker:
    def test_record_updates_current(self, tmp_path: Path):
        tracker = RateLimitTracker("token_suffix_12345678", "forgejo", "owner")
        tracker._STORAGE_DIR = tmp_path
        tracker._path = tmp_path / "forgejo-owner-12345678.json"

        snapshot = RateLimitSnapshot.from_response_headers(F.full_headers)
        tracker.record(snapshot)
        assert tracker.current.remaining == 4990
        assert tracker.current.limit == 5000

    def test_persist_and_load_roundtrip(self, tmp_path: Path):
        F.write_persisted_state(tmp_path, "forgejo", "owner", "12345678")

        tracker = RateLimitTracker("token_suffix_12345678", "forgejo", "owner")
        tracker._STORAGE_DIR = tmp_path
        tracker._path = tmp_path / "forgejo-owner-12345678.json"
        tracker._load()

        assert tracker.current.limit == 5000
        assert tracker.current.remaining == 100
        assert tracker.current.used == 4900

    def test_load_missing_file_no_error(self, tmp_path: Path):
        tracker = RateLimitTracker("token_none", "forgejo", "owner")
        tracker._STORAGE_DIR = tmp_path
        tracker._path = tmp_path / "nonexistent.json"
        tracker._load()
        assert tracker.current.remaining == 0

    def test_load_corrupt_file_no_error(self, tmp_path: Path):
        F.write_corrupt_state(tmp_path, "forgejo", "owner", "none")

        tracker = RateLimitTracker("token_none", "forgejo", "owner")
        tracker._STORAGE_DIR = tmp_path
        tracker._path = tmp_path / "forgejo-owner-none.json"
        tracker._load()
        assert tracker.current.remaining == 0

    def test_log_to_file_writes_summary(self, tmp_path: Path):
        tracker = RateLimitTracker("token_suffix_12345678", "forgejo", "owner")
        tracker._STORAGE_DIR = tmp_path
        tracker._path = tmp_path / "forgejo-owner-12345678.json"
        tracker.current = RateLimitSnapshot.from_response_headers(F.full_headers)

        buf = io.StringIO()
        tracker.log_to_file(buf)
        output = buf.getvalue()
        assert "Rate-Limit" in output
        assert "forgejo/owner" in output
        assert "4990/5000" in output
