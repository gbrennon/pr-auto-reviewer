from __future__ import annotations

from dataclasses import replace

import pytest

from pr_auto_reviewer.application.dtos.daemon_status_snapshot import (
    DaemonStatusSnapshot,
)
from pr_auto_reviewer.domain.value_objects.daemon_runtime_status import (
    DaemonRuntimeStatus,
)
from pr_auto_reviewer.domain.value_objects.daemon_state import DaemonState
from pr_auto_reviewer.presentation.status_dashboard import StatusDashboard

class TestStatusDashboard:
    @pytest.mark.asyncio
    async def test_renders_idle_snapshot_and_exits_with_q(self) -> None:
        status = DaemonRuntimeStatus(
            pid=1234,
            daemon_mode=True,
            state=DaemonState.IDLE,
            updated_at="2026-11-09T18:00:00Z",
            poll_interval_seconds=60,
            allowed_repositories=("owner/repo",),
            current_cycle=2,
        )
        snapshot = DaemonStatusSnapshot(
            runtime_status=status,
            daemon_alive=True,
            allowed_repositories=("owner/repo",),
            capabilities=(),
        )

        async with StatusDashboard(lambda: snapshot).run_test() as pilot:
            assert str(pilot.app.query_one("#state").render()) == "IDLE / WAITING"
            assert "owner/repo" in str(pilot.app.query_one("#repositories").render())
            await pilot.press("q")

        assert pilot.app.return_value is None

    @pytest.mark.asyncio
    async def test_renders_provider_error_without_crashing(self) -> None:
        def failing_provider() -> DaemonStatusSnapshot:
            raise RuntimeError("status store unavailable")

        async with StatusDashboard(failing_provider).run_test() as pilot:
            assert "status store unavailable" in str(pilot.app.query_one("#error").render())
            await pilot.press("q")

    @pytest.mark.asyncio
    async def test_refreshes_widget_content_from_new_snapshot(self) -> None:
        initial = DaemonStatusSnapshot(
            runtime_status=None,
            daemon_alive=False,
            allowed_repositories=(),
            capabilities=(),
        )
        updated_status = DaemonRuntimeStatus(
            pid=1234,
            daemon_mode=True,
            state=DaemonState.IDLE,
            updated_at="2026-11-09T18:00:00Z",
            poll_interval_seconds=60,
            allowed_repositories=(),
            current_cycle=3,
        )
        updated = replace(
            initial,
            runtime_status=updated_status,
            daemon_alive=True,
        )
        snapshots = iter((initial, updated))

        async with StatusDashboard(lambda: next(snapshots)).run_test() as pilot:
            assert "STOPPED" in str(pilot.app.query_one("#state").render())
            pilot.app.refresh_status()
            assert str(pilot.app.query_one("#state").render()) == "IDLE / WAITING"
            await pilot.press("q")
