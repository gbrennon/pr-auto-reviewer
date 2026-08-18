"""Behavioral tests for RepoUpdateTracker using an isolated storage dir."""

import json

from pr_auto_reviewer.infrastructure.client.repo_update_tracker import (
    RepoUpdateTracker,
)


def _tracker(storage_dir) -> RepoUpdateTracker:
    tracker = RepoUpdateTracker()
    tracker._STORAGE_DIR = storage_dir
    return tracker


class TestRepoUpdateTracker:
    """Exercises RepoUpdateTracker staleness and persistence rules."""

    def test_is_stale_when_pushed_at_none_then_true(self, tmp_path) -> None:
        assert _tracker(tmp_path).is_stale("o/r", None) is True

    def test_is_stale_when_no_file_then_true(self, tmp_path) -> None:
        assert _tracker(tmp_path).is_stale("o/r", "abc") is True

    def test_is_stale_when_unchanged_then_false(self, tmp_path) -> None:
        tracker = _tracker(tmp_path)
        tracker.mark_seen("o/r", "abc")

        assert tracker.is_stale("o/r", "abc") is False

    def test_is_stale_when_changed_then_true(self, tmp_path) -> None:
        tracker = _tracker(tmp_path)
        tracker.mark_seen("o/r", "abc")

        assert tracker.is_stale("o/r", "def") is True

    def test_is_stale_when_corrupt_json_then_true(self, tmp_path) -> None:
        (tmp_path / "o-r.json").write_text("not json")

        assert _tracker(tmp_path).is_stale("o/r", "abc") is True

    def test_mark_seen_then_file_persisted(self, tmp_path) -> None:
        tracker = _tracker(tmp_path)

        tracker.mark_seen("owner/repo", "abc")

        stored = json.loads((tmp_path / "owner-repo.json").read_text())
        assert stored == {"pushed_at": "abc"}

    def test_mark_seen_when_dir_unwritable_then_no_raise(self, tmp_path) -> None:
        blocker = tmp_path / "blocker"
        blocker.write_text("occupied")
        tracker = _tracker(blocker)

        tracker.mark_seen("o/r", "abc")

    def test_slugify_replaces_path_separators(self) -> None:
        assert RepoUpdateTracker()._slugify("owner/repo") == "owner-repo"