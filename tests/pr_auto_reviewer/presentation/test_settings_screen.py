from __future__ import annotations

import pytest
from textual.widgets import Button

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
    @pytest.mark.asyncio
    async def test_save_button_persists_setting_without_rendering_value(self) -> None:
        snapshot = DaemonStatusSnapshot(
            runtime_status=None,
            daemon_alive=False,
            allowed_repositories=(),
            capabilities=(),
        )
        settings = FakeSettings()

        async with StatusDashboard(lambda: snapshot, settings=settings).run_test() as pilot:
            await pilot.press("e")
            screen = pilot.app.screen
            screen.query_one("#setting-name").value = "POLL_INTERVAL"
            screen.query_one("#setting-value").value = "30"
            screen.on_button_pressed(Button.Pressed(screen.query_one("#save-setting")))
            assert settings.writes == [("POLL_INTERVAL", "30")]
            assert "30" not in str(screen.query_one("#settings-list").render())
            await pilot.press("q")

    @pytest.mark.asyncio
    async def test_repository_buttons_forward_role_tokens_without_rendering_them(self) -> None:
        snapshot = DaemonStatusSnapshot(
            runtime_status=None,
            daemon_alive=False,
            allowed_repositories=(),
            capabilities=(),
        )
        settings = FakeSettings()

        async with StatusDashboard(lambda: snapshot, settings=settings).run_test() as pilot:
            await pilot.press("e")
            screen = pilot.app.screen
            screen.query_one("#repository").value = "github:acme/widget"
            screen.query_one("#manager-token").value = "manager-secret"
            screen.query_one("#reviewer-token").value = "reviewer-secret"
            screen.on_button_pressed(Button.Pressed(screen.query_one("#add-repository")))
            assert settings.writes == [("github:acme/widget", "manager-secretreviewer-secret")]
            assert "manager-secret" not in str(screen.render())
            assert "reviewer-secret" not in str(screen.render())
            await pilot.press("q")

    @pytest.mark.asyncio
    async def test_vim_j_can_select_save_button(self) -> None:
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
            screen = pilot.app.screen
            screen.query_one("#setting-name").focus()
            await pilot.press(*(["j"] * 7))
            assert pilot.app.focused.id == "save-setting"
            await pilot.press("q")

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
