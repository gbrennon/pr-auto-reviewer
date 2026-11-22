from __future__ import annotations

from dataclasses import replace

import pytest
from textual.widgets import Button

from pr_auto_reviewer.application.dtos.daemon_status_snapshot import (
    DaemonStatusSnapshot,
)
from pr_auto_reviewer.domain.entities.api_access_capability import (
    ApiAccessCapability,
)
from pr_auto_reviewer.domain.value_objects.active_review_progress import (
    ActiveReviewProgress,
)
from pr_auto_reviewer.domain.value_objects.daemon_runtime_status import (
    DaemonRuntimeStatus,
)
from pr_auto_reviewer.domain.value_objects.daemon_state import DaemonState
from pr_auto_reviewer.presentation.cli.settings_cli import SettingsSnapshot
from pr_auto_reviewer.presentation.status_dashboard import StatusDashboard

class FakeSettings:
    def __init__(self) -> None:
        self.writes: list[tuple[str, str]] = []
        self.snapshot_value = SettingsSnapshot(
            values=(("poll_interval", "60"),),
            secret_names=("GITHUB_TOKEN",),
        )

    def snapshot(self) -> SettingsSnapshot:
        return self.snapshot_value

    def write(self, name: str, value: str) -> None:
        self.writes.append((name, value))

    def unset(self, name: str) -> None:
        self.writes.append((name, ""))

    def add_repository(self, repository: str, manager_token: str, reviewer_token: str) -> None:
        self.writes.append((repository, manager_token + reviewer_token))

    def remove_repository(self, repository: str) -> None:
        self.writes.append((repository, ""))

class TestStatusDashboard:
    @pytest.mark.asyncio
    async def test_renders_grouped_status_items_in_one_table(self) -> None:
        review = ActiveReviewProgress(
            repository="forgejo:owner/repo",
            pr_number=42,
            pr_title="PR Title",
            head_sha="abc1234",
            started_at="2026-11-09T18:00:00Z",
            phase_name="Architecture",
            current_turn=2,
            max_turns=5,
        )
        status = DaemonRuntimeStatus(
            pid=1234,
            daemon_mode=True,
            state=DaemonState.REVIEWING,
            updated_at="2026-11-09T18:00:00Z",
            poll_interval_seconds=60,
            allowed_repositories=(
                "forgejo:owner/repo",
                "github:other/project",
            ),
            current_cycle=2,
            current_review=review,
        )
        snapshot = DaemonStatusSnapshot(
            runtime_status=status,
            daemon_alive=True,
            allowed_repositories=status.allowed_repositories,
            capabilities=(
                ApiAccessCapability(
                    platform="github",
                    role="reviewer",
                    source_name="GITHUB_TOKEN",
                    scope="other/project",
                ),
                ApiAccessCapability(
                    platform="github",
                    role="reviewer",
                    source_name="GITHUB_TOKEN",
                    scope="another/project",
                ),
            ),
        )

        async with StatusDashboard(lambda: snapshot).run_test() as pilot:
            table = pilot.app.query_one("#items")
            assert table.row_count == 5
            assert "REVIEWING" in str(pilot.app.query_one("#state").render())
            assert "Sort: platform" in str(pilot.app.query_one("#sort").render())
            await pilot.press("q")

    @pytest.mark.asyncio
    async def test_cycles_user_selected_sorting(self) -> None:
        snapshot = DaemonStatusSnapshot(
            runtime_status=None,
            daemon_alive=False,
            allowed_repositories=("github:owner/repo",),
            capabilities=(),
        )

        async with StatusDashboard(lambda: snapshot).run_test() as pilot:
            assert "Sort: platform" in str(pilot.app.query_one("#sort").render())
            await pilot.press("s")
            assert "Sort: repository" in str(pilot.app.query_one("#sort").render())
            await pilot.press("s")
            assert "Sort: status" in str(pilot.app.query_one("#sort").render())
            await pilot.press("q")

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_settings_panel_shows_secret_storage_setup_error(self) -> None:
        snapshot = DaemonStatusSnapshot(
            runtime_status=None,
            daemon_alive=False,
            allowed_repositories=(),
            capabilities=(),
        )
        settings = FakeSettings()
        settings.snapshot_value = SettingsSnapshot(
            values=(("poll_interval", "60"),),
            secret_names=(),
            secret_error="PR_AUTO_REVIEWER_ENCRYPTION_KEY is required",
        )

        async with StatusDashboard(lambda: snapshot, settings=settings).run_test() as pilot:
            await pilot.press("e")
            rendered = str(pilot.app.query_one("#settings-list").render())
            assert "Secret storage unavailable" in rendered
            assert "PR_AUTO_REVIEWER_ENCRYPTION_KEY is required" in rendered
            await pilot.press("q")

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_changes_navigation_mode_from_settings_panel(self) -> None:
        snapshot = DaemonStatusSnapshot(
            runtime_status=None,
            daemon_alive=False,
            allowed_repositories=(),
            capabilities=(),
        )
        settings = FakeSettings()

        async with StatusDashboard(lambda: snapshot, settings=settings).run_test() as pilot:
            await pilot.press("e")
            pilot.app.query_one("#navigation-mode").value = "vim"
            await pilot.pause()
            assert ("TUI_NAVIGATION_MODE", "vim") in settings.writes
            await pilot.press("q")

    @pytest.mark.asyncio
    async def test_supports_refresh_pause_and_settings_actions(self) -> None:
        snapshot = DaemonStatusSnapshot(
            runtime_status=None,
            daemon_alive=False,
            allowed_repositories=(),
            capabilities=(),
        )
        settings = FakeSettings()

        async with StatusDashboard(lambda: snapshot, settings=settings).run_test(size=(120, 40)) as pilot:
            await pilot.press("p")
            assert "paused" in str(pilot.app.query_one("#action-status").render()).lower()
            await pilot.press("p")
            assert "live" in str(pilot.app.query_one("#action-status").render()).lower()
            await pilot.press("e")
            assert pilot.app.query_one("#settings").styles.display == "block"
            pilot.app.query_one("#setting-name").value = "GITHUB_TOKEN"
            pilot.app.query_one("#setting-value").value = "new-secret"
            pilot.app.on_button_pressed(
                Button.Pressed(pilot.app.query_one("#save-setting"))
            )
            assert settings.writes == [("GITHUB_TOKEN", "new-secret")]
            assert "new-secret" not in str(pilot.app.query_one("#settings").render())
            await pilot.press("q")

    @pytest.mark.asyncio
    async def test_refresh_updates_changed_cells_without_resetting_cursor(self) -> None:
        initial_review = ActiveReviewProgress(
            repository="forgejo:owner/repo",
            pr_number=42,
            pr_title="PR Title",
            head_sha="abc1234",
            started_at="2026-11-09T18:00:00Z",
            phase_name="Architecture",
            current_turn=1,
            max_turns=5,
        )
        updated_review = replace(initial_review, current_turn=2)
        initial_status = DaemonRuntimeStatus(
            pid=1234,
            daemon_mode=True,
            state=DaemonState.REVIEWING,
            updated_at="2026-11-09T18:00:00Z",
            poll_interval_seconds=60,
            allowed_repositories=("forgejo:owner/repo",),
            current_cycle=2,
            current_review=initial_review,
        )
        updated_status = replace(initial_status, current_review=updated_review)
        initial = DaemonStatusSnapshot(
            runtime_status=initial_status,
            daemon_alive=True,
            allowed_repositories=initial_status.allowed_repositories,
            capabilities=(),
        )
        updated = replace(initial, runtime_status=updated_status)
        snapshots = iter((initial, updated))

        async with StatusDashboard(lambda: next(snapshots)).run_test() as pilot:
            table = pilot.app.query_one("#items")
            table.move_cursor(row=1)
            cursor_key = list(table.rows)[table.cursor_row]
            pilot.app.refresh_status()

            assert table.cursor_row == 1
            assert list(table.rows)[table.cursor_row] == cursor_key
            assert "turn 2/5" in " ".join(str(cell) for cell in table.get_row(cursor_key))
            await pilot.press("q")

    @pytest.mark.asyncio
    async def test_renders_provider_error_without_crashing(self) -> None:
        def failing_provider() -> DaemonStatusSnapshot:
            raise RuntimeError("status store unavailable")

        async with StatusDashboard(failing_provider).run_test() as pilot:
            assert "status store unavailable" in str(pilot.app.query_one("#error").render())
            await pilot.press("q")

    @pytest.mark.asyncio
    async def test_automatically_refreshes_from_provider_on_timer(self) -> None:
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
            current_cycle=1,
        )
        updated = replace(initial, runtime_status=updated_status, daemon_alive=True)
        snapshots = iter((initial, updated, updated))

        async with StatusDashboard(lambda: next(snapshots)).run_test() as pilot:
            await pilot.pause(delay=1.1)
            assert "IDLE / WAITING" in str(pilot.app.query_one("#state").render())
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
        updated = replace(initial, runtime_status=updated_status, daemon_alive=True)
        snapshots = iter((initial, updated))

        async with StatusDashboard(lambda: next(snapshots)).run_test() as pilot:
            assert "STOPPED" in str(pilot.app.query_one("#state").render())
            pilot.app.refresh_status()
            assert "IDLE / WAITING" in str(pilot.app.query_one("#state").render())
            await pilot.press("q")
