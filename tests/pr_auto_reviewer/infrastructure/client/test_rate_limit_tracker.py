"""Tests for RateLimitTracker using captured fixtures."""

import io
import time
from pathlib import Path

from pr_auto_reviewer.domain.value_objects.token_slug import TokenSlug
from pr_auto_reviewer.infrastructure.client.rate_limit_snapshot import RateLimitSnapshot
from pr_auto_reviewer.infrastructure.client.rate_limit_tracker import RateLimitTracker
from tests.fixtures.rate_limit_fixtures import RateLimitFixtures as F


class TestRateLimitTracker:
    def test_record_updates_current(self, tmp_path: Path):
        tracker = RateLimitTracker(TokenSlug("token_suffix_12345678"), "forgejo", "owner")
        tracker._store._STORAGE_DIR = tmp_path
        tracker._store._path = tmp_path / "forgejo-owner-12345678.json"

        snapshot = RateLimitSnapshot.from_response_headers(F.full_headers)
        tracker.record(snapshot)
        assert tracker.current.remaining == 4990
        assert tracker.current.limit == 5000

    def test_persist_and_load_roundtrip(self, tmp_path: Path):
        F.write_persisted_state(tmp_path, "forgejo", "owner", "12345678")

        tracker = RateLimitTracker(TokenSlug("token_suffix_12345678"), "forgejo", "owner")
        tracker._store._STORAGE_DIR = tmp_path
        tracker._store._path = tmp_path / "forgejo-owner-12345678.json"
        tracker.current = tracker._store.load()

        assert tracker.current.limit == 5000
        assert tracker.current.remaining == 100
        assert tracker.current.used == 4900

    def test_load_missing_file_no_error(self, tmp_path: Path):
        tracker = RateLimitTracker(TokenSlug("token_none"), "forgejo", "owner")
        tracker._store._STORAGE_DIR = tmp_path
        tracker._store._path = tmp_path / "nonexistent.json"
        tracker.current = tracker._store.load()
        assert tracker.current.remaining == 0

    def test_load_corrupt_file_no_error(self, tmp_path: Path):
        F.write_corrupt_state(tmp_path, "forgejo", "owner", "none")

        tracker = RateLimitTracker(TokenSlug("token_none"), "forgejo", "owner")
        tracker._store._STORAGE_DIR = tmp_path
        tracker._store._path = tmp_path / "forgejo-owner-none.json"
        tracker.current = tracker._store.load()
        assert tracker.current.remaining == 0

    def test_log_to_file_writes_summary(self, tmp_path: Path):
        tracker = RateLimitTracker(TokenSlug("token_suffix_12345678"), "forgejo", "owner")
        tracker._store._STORAGE_DIR = tmp_path
        tracker._store._path = tmp_path / "forgejo-owner-12345678.json"
        tracker.current = RateLimitSnapshot.from_response_headers(F.full_headers)

        buf = io.StringIO()
        tracker.log_to_file(buf)
        output = buf.getvalue()
        assert "Rate-Limit" in output
        assert "forgejo/owner" in output
        assert "4990/5000" in output

    def test_record_exhausted_logs_warning(self, tmp_path: Path, caplog):
        tracker = RateLimitTracker(TokenSlug("token_suffix_12345678"), "forgejo", "owner")
        tracker._store._STORAGE_DIR = tmp_path
        tracker._store._path = tmp_path / "forgejo-owner-12345678.json"

        snapshot = RateLimitSnapshot.from_response_headers(F.exhausted_headers)
        tracker.record(snapshot)
        assert "EXHAUSTED" in caplog.text

    def test_wait_skips_when_remaining_above_min(self, tmp_path: Path):
        tracker = RateLimitTracker(TokenSlug("token_suffix_12345678"), "forgejo", "owner")
        tracker._store._STORAGE_DIR = tmp_path
        tracker._store._path = tmp_path / "forgejo-owner-12345678.json"
        tracker.current = RateLimitSnapshot.from_response_headers(F.full_headers)

        # remaining=4990 >= min_remaining=5 → should return immediately
        tracker.wait(min_remaining=5)

    def test_wait_skips_when_not_exhausted_but_low(self, tmp_path: Path):
        tracker = RateLimitTracker(TokenSlug("token_suffix_12345678"), "forgejo", "owner")
        tracker._store._STORAGE_DIR = tmp_path
        tracker._store._path = tmp_path / "forgejo-owner-12345678.json"
        tracker.current = RateLimitSnapshot(
            limit=5000, remaining=3, used=4997,
            reset=int(time.time()) + 3600, resource="core",
        )

        # not exhausted (remaining=3 > 0) → should return immediately
        tracker.wait(min_remaining=5)

    def test_wait_waits_when_exhausted(self, tmp_path: Path, monkeypatch):
        tracker = RateLimitTracker(TokenSlug("token_suffix_12345678"), "forgejo", "owner")
        tracker._store._STORAGE_DIR = tmp_path
        tracker._store._path = tmp_path / "forgejo-owner-12345678.json"
        tracker.current = RateLimitSnapshot.from_response_headers(F.exhausted_headers)

        sleep_calls = []
        monkeypatch.setattr(time, "sleep", lambda s: sleep_calls.append(s))
        tracker.wait()
        assert len(sleep_calls) == 1

    def test_wait_waits_default_when_reset_passed(self, tmp_path: Path, monkeypatch):
        tracker = RateLimitTracker(TokenSlug("token_suffix_12345678"), "forgejo", "owner")
        tracker._store._STORAGE_DIR = tmp_path
        tracker._store._path = tmp_path / "forgejo-owner-12345678.json"
        tracker.current = RateLimitSnapshot(
            limit=5000, remaining=0, used=5000,
            reset=int(time.time()) - 60, resource="core",
        )

        sleep_calls = []
        monkeypatch.setattr(time, "sleep", lambda s: sleep_calls.append(s))
        tracker.wait()
        assert len(sleep_calls) == 1
        assert sleep_calls[0] == 60

    def test_persist_oserror_silent(self, tmp_path: Path):
        tracker = RateLimitTracker(TokenSlug("token_suffix_12345678"), "forgejo", "owner")
        tracker._store._STORAGE_DIR = tmp_path
        tracker._store._path = Path("/nonexistent_dir_should_not_exist/sub/file.json")
        tracker.current = RateLimitSnapshot.from_response_headers(F.full_headers)

        # should not raise
        tracker._store.save(tracker.current)

    def test_token_slug_empty_token(self):
        assert TokenSlug("").value == "none"

    def test_token_slug_last_8_chars(self):
        assert TokenSlug("ghp_abcdefgh12345678").value == "12345678"

    def test_token_slug_short_token(self):
        assert TokenSlug("abc").value == "abc"
