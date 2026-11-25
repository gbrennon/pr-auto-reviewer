from __future__ import annotations

import pytest
from textual.widgets import Button, Input, Select

from pr_auto_reviewer.application.dtos.daemon_status_snapshot import DaemonStatusSnapshot
from pr_auto_reviewer.presentation.cli.settings_cli import SettingsSnapshot
from pr_auto_reviewer.presentation.general_settings_screen import GeneralSettingsScreen
from pr_auto_reviewer.presentation.global_credentials_screen import GlobalCredentialsScreen
from pr_auto_reviewer.presentation.repository_credentials_screen import (
    RepositoryCredentialsScreen,
)
from pr_auto_reviewer.presentation.repository_management_screen import (
    RepositoryManagementScreen,
)
from pr_auto_reviewer.presentation.settings_models import RepositoryCredentialStatus
from pr_auto_reviewer.presentation.settings_screen import SettingsScreen
from pr_auto_reviewer.presentation.status_dashboard import StatusDashboard
from tests.pr_auto_reviewer.presentation.test_status_dashboard import FakeSettings


class TestSettingsScreen:
    """Verify explicit settings navigation and credential forms."""

    @pytest.mark.asyncio
    async def test_home_actions_render_at_constrained_size(self) -> None:
        snapshot = DaemonStatusSnapshot(
            runtime_status=None,
            daemon_alive=False,
            allowed_repositories=(),
            capabilities=(),
        )

        async with StatusDashboard(
            lambda: snapshot,
            settings=FakeSettings(),
        ).run_test(size=(48, 12)) as pilot:
            await pilot.press("e")
            screen = pilot.app.screen
            assert isinstance(screen, SettingsScreen)
            assert [
                button.id for button in screen.query(Button)
            ] == [
                "repository-management",
                "general-settings",
                "global-credentials",
                "repository-credentials",
            ]
            for button_id in (
                "repository-management",
                "general-settings",
                "global-credentials",
                "repository-credentials",
            ):
                button = screen.query_one(f"#{button_id}")
                button.focus(scroll_visible=True)
                await pilot.pause(0.3)
                assert pilot.app.focused is button
                assert screen.can_view_entire(button)

    @pytest.mark.asyncio
    async def test_general_settings_iterates_known_keys_and_masks_secrets(self) -> None:
        snapshot = DaemonStatusSnapshot(
            runtime_status=None,
            daemon_alive=False,
            allowed_repositories=(),
            capabilities=(),
        )
        settings = FakeSettings()
        settings.snapshot_value = SettingsSnapshot(
            values=(("daemon.debug", "1"), ("llm.model", "qwen")),
            secret_names=("GITHUB_MANAGER_TOKEN", "PR_AUTO_REVIEWER_ENCRYPTION_KEY"),
            secret_error="PR_AUTO_REVIEWER_ENCRYPTION_KEY is required",
        )

        async with StatusDashboard(lambda: snapshot, settings=settings).run_test() as pilot:
            await pilot.press("e")
            await pilot.click("#general-settings")
            screen = pilot.app.screen
            assert isinstance(screen, GeneralSettingsScreen)
            key_select = screen.query_one("#setting-key", Select)
            value_input = screen.query_one("#setting-value", Input)
            assert key_select.value == "daemon.debug"
            assert value_input.value == "1"
            key_select.value = "PR_AUTO_REVIEWER_ENCRYPTION_KEY"
            await pilot.pause()
            assert value_input.value == ""
            assert "Secret storage unavailable: PR_AUTO_REVIEWER_ENCRYPTION_KEY is required" in str(
                screen.query_one("#settings-list").render()
            )
            value_input.value = "replacement-key"
            save = screen.query_one("#save-setting", Button)
            save.focus()
            await pilot.press("enter")
            assert ("PR_AUTO_REVIEWER_ENCRYPTION_KEY", "replacement-key") in settings.writes
            assert "replacement-key" not in str(screen.render())

    @pytest.mark.asyncio
    async def test_global_credentials_form_saves_without_rendering_token(self) -> None:
        snapshot = DaemonStatusSnapshot(
            runtime_status=None,
            daemon_alive=False,
            allowed_repositories=(),
            capabilities=(),
        )
        settings = FakeSettings()

        async with StatusDashboard(lambda: snapshot, settings=settings).run_test() as pilot:
            await pilot.press("e")
            await pilot.click("#global-credentials")
            screen = pilot.app.screen
            assert isinstance(screen, GlobalCredentialsScreen)
            screen.query_one("#token").value = "global-secret"
            save = screen.query_one("#save", Button)
            save.focus()
            await pilot.press("enter")
            assert settings.global_credentials == [("github", "manager", "global-secret")]
            assert "global-secret" not in str(screen.render())

    @pytest.mark.asyncio
    async def test_global_credentials_reports_missing_encryption_configuration(self) -> None:
        snapshot = DaemonStatusSnapshot(
            runtime_status=None,
            daemon_alive=False,
            allowed_repositories=(),
            capabilities=(),
        )
        settings = FakeSettings()
        settings.global_error = "PR_AUTO_REVIEWER_ENCRYPTION_KEY is required"

        async with StatusDashboard(lambda: snapshot, settings=settings).run_test() as pilot:
            await pilot.press("e")
            await pilot.click("#global-credentials")
            screen = pilot.app.screen
            assert isinstance(screen, GlobalCredentialsScreen)
            save = screen.query_one("#save", Button)
            save.focus()
            await pilot.press("enter")
            error = screen.query_one("#error").render()
            assert "Credential error" in str(error)
            assert "ENCRYPTION_KEY is required" in str(error)

    @pytest.mark.asyncio
    async def test_repository_credentials_keep_roles_independently_optional(self) -> None:
        snapshot = DaemonStatusSnapshot(
            runtime_status=None,
            daemon_alive=False,
            allowed_repositories=(),
            capabilities=(),
        )
        settings = FakeSettings()

        async with StatusDashboard(lambda: snapshot, settings=settings).run_test() as pilot:
            await pilot.press("e")
            await pilot.click("#repository-credentials")
            screen = pilot.app.screen
            assert isinstance(screen, RepositoryCredentialsScreen)
            screen.query_one("#repository").value = "acme/widget"
            screen.query_one("#manager-token").value = "manager-secret"
            save = screen.query_one("#save", Button)
            save.focus()
            await pilot.press("enter")
            assert settings.repository_credentials == [
                ("github:acme/widget", "manager-secret", "")
            ]
            assert "manager-secret" not in str(screen.render())


    @pytest.mark.asyncio
    async def test_repository_management_shows_credential_error_details(self) -> None:
        snapshot = DaemonStatusSnapshot(
            runtime_status=None,
            daemon_alive=False,
            allowed_repositories=(),
            capabilities=(),
        )
        settings = FakeSettings()
        settings.repository_statuses = (
            RepositoryCredentialStatus(
                "forgejo:owner/repo",
                "error",
                "error",
                manager_error="encryption key is invalid",
                reviewer_error="secret storage unavailable",
            ),
        )

        async with StatusDashboard(lambda: snapshot, settings=settings).run_test() as pilot:
            await pilot.press("e")
            await pilot.click("#repository-management")
            screen = pilot.app.screen
            assert isinstance(screen, RepositoryManagementScreen)
            rendered = str(screen.query_one("#repository-list").render())
            assert "manager: error — encryption key is invalid" in rendered
            assert "reviewer: error — secret storage unavailable" in rendered

