from __future__ import annotations

from unittest.mock import MagicMock

from pr_auto_reviewer.application.services.show_status_service import (
    ShowStatusService,
)
from pr_auto_reviewer.domain.value_objects.daemon_runtime_status import (
    DaemonRuntimeStatus,
)
from pr_auto_reviewer.domain.value_objects.daemon_state import DaemonState

class TestShowStatusSnapshot:
    def test_returns_live_runtime_data_and_configured_repositories(self) -> None:
        state_port = MagicMock()
        status = DaemonRuntimeStatus(
            pid=1234,
            daemon_mode=True,
            state=DaemonState.IDLE,
            updated_at="2026-11-09T18:00:00Z",
            poll_interval_seconds=60,
            allowed_repositories=("owner/repo",),
            current_cycle=2,
        )
        state_port.read_status.return_value = status
        service = ShowStatusService(
            runtime_state=state_port,
            process_checker=lambda pid: True,
            allowed_repositories=("owner/repo",),
        )

        snapshot = service.snapshot()

        assert snapshot.runtime_status == status
        assert snapshot.daemon_alive is True
        assert snapshot.allowed_repositories == ("owner/repo",)
        assert snapshot.capabilities == ()

    def test_returns_stopped_snapshot_when_runtime_pid_is_not_alive(self) -> None:
        state_port = MagicMock()
        status = DaemonRuntimeStatus(
            pid=4321,
            daemon_mode=True,
            state=DaemonState.IDLE,
            updated_at="2026-11-09T18:00:00Z",
            poll_interval_seconds=60,
            allowed_repositories=(),
            current_cycle=2,
        )
        state_port.read_status.return_value = status
        service = ShowStatusService(
            runtime_state=state_port,
            process_checker=lambda pid: False,
            allowed_repositories=(),
        )

        snapshot = service.snapshot()

        assert snapshot.runtime_status == status
        assert snapshot.daemon_alive is False

    def test_returns_missing_runtime_snapshot(self) -> None:
        state_port = MagicMock()
        state_port.read_status.return_value = None
        service = ShowStatusService(
            runtime_state=state_port,
            process_checker=lambda pid: False,
            allowed_repositories=("owner/repo",),
        )

        snapshot = service.snapshot()

        assert snapshot.runtime_status is None
        assert snapshot.daemon_alive is False
        assert snapshot.allowed_repositories == ("owner/repo",)
