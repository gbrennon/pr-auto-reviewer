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

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_emacs_ctrl_p_moves_to_previous_field_instead_of_opening_palette(self) -> None:
        snapshot = DaemonStatusSnapshot(
            runtime_status=None,
            daemon_alive=False,
            allowed_repositories=(),
            capabilities=(),
        )

        async with StatusDashboard(
            lambda: snapshot,
            settings=FakeSettings(),
            navigation_mode=NavigationMode.EMACS,
        ).run_test() as pilot:
            await pilot.press("e")
            screen = pilot.app.screen
            screen.query_one("#repository").focus()
            await pilot.press("ctrl+p")
            assert pilot.app.focused.id == "setting-name"
            assert not pilot.app.query("#command-palette")
            await pilot.press("q")

    @pytest.mark.asyncio
    async def test_back_keys_work_while_vim_input_has_focus(self) -> None:
        snapshot = DaemonStatusSnapshot(
            runtime_status=None,
            daemon_alive=False,
            allowed_repositories=(),
            capabilities=(),
        )

        async with StatusDashboard(
            lambda: snapshot,
            settings=FakeSettings(),
            navigation_mode=NavigationMode.VIM,
        ).run_test() as pilot:
            await pilot.press("e")
            pilot.app.screen.query_one("#setting-name").focus()
            await pilot.press("q")
            assert not isinstance(pilot.app.screen, SettingsScreen)
