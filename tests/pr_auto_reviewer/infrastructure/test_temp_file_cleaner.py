"""TempFileCleaner tests."""

from __future__ import annotations

import os
import time
from pathlib import Path

from pr_auto_reviewer.infrastructure.temp_file_cleaner import clean_temp_files


class TestCleanTempFiles:
    def test_returns_zero_when_no_files(self, tmp_path: Path) -> None:
        deleted = clean_temp_files(target_dir=tmp_path)

        assert deleted == 0

    def test_deletes_only_old_files(self, tmp_path: Path) -> None:
        now = time.time()
        old_ts = now - 7200  # 2 hours ago

        # Old files (should be deleted)
        old_http = tmp_path / "http-old.log"
        old_http.write_text("old")
        os.utime(old_http, (old_ts, old_ts))

        old_prompt = tmp_path / "ollama-prompt-try1-old.txt"
        old_prompt.write_text("old")
        os.utime(old_prompt, (old_ts, old_ts))

        old_raw = tmp_path / "ollama_raw_response.txt"
        old_raw.write_text("old")
        os.utime(old_raw, (old_ts, old_ts))

        # New files (should survive)
        new_http = tmp_path / "http-new.log"
        new_http.write_text("new")

        new_prompt = tmp_path / "ollama-prompt-try2-new.txt"
        new_prompt.write_text("new")

        deleted = clean_temp_files(target_dir=tmp_path)

        assert deleted == 3
        assert not old_http.exists()
        assert not old_prompt.exists()
        assert not old_raw.exists()
        assert new_http.exists()
        assert new_prompt.exists()

    def test_handles_unlink_failure_gracefully(self, tmp_path: Path) -> None:
        """When unlink raises OSError, the function logs a warning and continues."""
        now = time.time()
        old_ts = now - 7200

        subdir = tmp_path / "readonly"
        subdir.mkdir()
        old_file = subdir / "http-old.log"
        old_file.write_text("old")
        os.utime(old_file, (old_ts, old_ts))

        # Remove write permission from the directory — glob still works
        # (needs r-x), but unlink fails (needs -w-).
        subdir.chmod(0o555)

        try:
            deleted = clean_temp_files(target_dir=subdir)
            assert deleted == 0
            assert old_file.exists()
        finally:
            subdir.chmod(0o755)

    def test_does_not_delete_non_matching_files(self, tmp_path: Path) -> None:
        now = time.time()
        old_ts = now - 7200

        # Non-matching old file
        other = tmp_path / "other-file.txt"
        other.write_text("unrelated")
        os.utime(other, (old_ts, old_ts))

        # Matching old file (should still be cleaned)
        matching = tmp_path / "http-clean.log"
        matching.write_text("clean")
        os.utime(matching, (old_ts, old_ts))

        deleted = clean_temp_files(target_dir=tmp_path)

        assert deleted == 1
        assert not matching.exists()
        assert other.exists()

    def test_respects_custom_max_age(self, tmp_path: Path) -> None:
        now = time.time()

        # 30 seconds old — should survive 60s threshold
        young_ts = now - 30
        young = tmp_path / "http-young.log"
        young.write_text("young")
        os.utime(young, (young_ts, young_ts))

        # 90 seconds old — should be deleted under 60s threshold
        old_ts = now - 90
        old = tmp_path / "ollama-prompt-old.txt"
        old.write_text("old")
        os.utime(old, (old_ts, old_ts))

        deleted = clean_temp_files(max_age_seconds=60, target_dir=tmp_path)

        assert deleted == 1
        assert young.exists()
        assert not old.exists()
