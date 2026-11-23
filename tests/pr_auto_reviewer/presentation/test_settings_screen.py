from __future__ import annotations

import pytest

from pr_auto_reviewer.application.dtos.daemon_status_snapshot import DaemonStatusSnapshot
from pr_auto_reviewer.presentation.navigation import NavigationMode
from pr_auto_reviewer.presentation.settings_screen import SettingsScreen
from pr_auto_reviewer.presentation.status_dashboard import StatusDashboard

from tests.pr_auto_reviewer.presentation.test_status_dashboard import FakeSettings


class TestSettingsScreen:
    @pytest.mark.asyncio
    async def test_settings_is_a_dedicated_screen_and_returns_to_dashboard(self) -> None:
        snapshot = DaemonStatusSnapshot(
            runtime_status=None,
            daemon_alive=False,
            allowed_repositories=(),
            capabilities=(),
        )

        async with StatusDashboard(
            lambda: snapshot,
            settings=FakeSettings(),
            navigation_mode=NavigationMode.ARROWS,
        ).run_test() as pilot:
            await pilot.press("e")
            assert isinstance(pilot.app.screen, SettingsScreen)
            await pilot.press("escape")
            assert not isinstance(pilot.app.screen, SettingsScreen)
            await pilot.press("q")
