from __future__ import annotations

from pathlib import Path

from pr_auto_reviewer.domain.value_objects.active_review_progress import (
    ActiveReviewProgress,
)
from pr_auto_reviewer.domain.value_objects.daemon_runtime_status import (
    DaemonRuntimeStatus,
)
from pr_auto_reviewer.domain.value_objects.daemon_state import DaemonState
from pr_auto_reviewer.infrastructure.persistence.json_daemon_runtime_state_store import (
    JsonDaemonRuntimeStateStore,
)


class TestJsonDaemonRuntimeStateStore:
    """Verifies atomic recording and deserialization of daemon runtime state."""

    def test_read_returns_none_when_state_file_does_not_exist(
        self, tmp_path: Path,
    ) -> None:
        state_path = tmp_path / "daemon-status.json"
        store = JsonDaemonRuntimeStateStore(state_path)

        result = store.read_status()

        assert result is None

    def test_record_and_read_idle_status(self, tmp_path: Path) -> None:
        state_path = tmp_path / "daemon-status.json"
        store = JsonDaemonRuntimeStateStore(state_path)
        status = DaemonRuntimeStatus(
            pid=12345,
            daemon_mode=True,
            state=DaemonState.IDLE,
            updated_at="2026-11-09T18:00:00Z",
            poll_interval_seconds=600,
            allowed_repositories=("repo/a", "repo/b"),
            current_cycle=2,
            next_cycle_at="2026-11-09T18:10:00Z",
        )

        store.record_status(status)
        result = store.read_status()

        assert result is not None
        assert result.pid == 12345
        assert result.daemon_mode is True
        assert result.state == DaemonState.IDLE
        assert result.poll_interval_seconds == 600
        assert result.allowed_repositories == ("repo/a", "repo/b")
        assert result.current_cycle == 2
        assert result.next_cycle_at == "2026-11-09T18:10:00Z"
        assert result.current_review is None

    def test_record_and_read_reviewing_status(self, tmp_path: Path) -> None:
        state_path = tmp_path / "daemon-status.json"
        store = JsonDaemonRuntimeStateStore(state_path)
        review = ActiveReviewProgress(
            repository="owner/repo",
            pr_number=42,
            pr_title="Add telemetry",
            head_sha="abc1234",
            started_at="2026-11-09T18:05:00Z",
            phase_name="Bug Hunt — Diff",
            phase_index=1,
            total_phases=3,
            subagent_role="engineer",
            current_turn=3,
            max_turns=11,
            last_tool_call="read_file",
            last_tool_args="src/main.py",
        )
        status = DaemonRuntimeStatus(
            pid=12345,
            daemon_mode=True,
            state=DaemonState.REVIEWING,
            updated_at="2026-11-09T18:06:00Z",
            poll_interval_seconds=600,
            allowed_repositories=("owner/repo",),
            current_cycle=1,
            current_review=review,
        )

        store.record_status(status)
        result = store.read_status()

        assert result is not None
        assert result.state == DaemonState.REVIEWING
        assert result.current_review is not None
        assert result.current_review.repository == "owner/repo"
        assert result.current_review.pr_number == 42
        assert result.current_review.phase_name == "Bug Hunt — Diff"
        assert result.current_review.subagent_role == "engineer"
        assert result.current_review.current_turn == 3
        assert result.current_review.last_tool_call == "read_file"

    def test_clear_removes_status_file(self, tmp_path: Path) -> None:
        state_path = tmp_path / "daemon-status.json"
        store = JsonDaemonRuntimeStateStore(state_path)
        status = DaemonRuntimeStatus(
            pid=12345,
            daemon_mode=True,
            state=DaemonState.IDLE,
            updated_at="2026-11-09T18:00:00Z",
            poll_interval_seconds=600,
            allowed_repositories=(),
        )
        store.record_status(status)
        assert state_path.exists()

        store.clear()

        assert not state_path.exists()
        assert store.read_status() is None
