from __future__ import annotations

from collections.abc import Callable
from textual.app import ComposeResult

from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, Static

from pr_auto_reviewer.presentation.settings_services_port import SettingsServicesPort
from pr_auto_reviewer.presentation.general_settings_screen import GeneralSettingsScreen
from pr_auto_reviewer.presentation.global_credentials_screen import GlobalCredentialsScreen
from pr_auto_reviewer.presentation.navigation import NavigationMode
from pr_auto_reviewer.presentation.repository_credentials_screen import RepositoryCredentialsScreen
from pr_auto_reviewer.presentation.repository_management_screen import RepositoryManagementScreen


class SettingsScreen(Screen[None]):
    """Settings home screen with explicit actions and no unlabeled form fields."""

    CSS = """
    Screen { layout: vertical; overflow-y: auto; }
    #settings-title { margin: 1; text-style: bold; }
    #settings-help { margin: 0 1; }
    .settings-action { margin: 1 1 0 1; height: 3; }
    #action-status, #error { margin: 1; }
    #error { color: $error; }
    """
    BINDINGS = [
        Binding("q", "back", "Back", priority=True),
        Binding("escape", "back", "Back", priority=True),
    ]

    def __init__(
        self,
        settings: SettingsServicesPort,
        navigation_mode: NavigationMode,
        on_navigation_mode_changed: Callable[[NavigationMode], None] | None = None,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._navigation_mode = navigation_mode
        self._on_navigation_mode_changed = on_navigation_mode_changed

    def compose(self) -> ComposeResult:
        yield Static("Settings", id="settings-title")
        yield Static(
            "Choose an action. Credential values are write-only.",
            id="settings-help",
        )
        yield Button(
            "Repository management",
            id="repository-management",
            classes="settings-action",
        )
        yield Button("General settings", id="general-settings", classes="settings-action")
        yield Button("Global credentials", id="global-credentials", classes="settings-action")
        yield Button(
            "Repository credentials",
            id="repository-credentials",
            classes="settings-action",
        )
        yield Static("", id="action-status")
        yield Static("", id="error")

    def action_back(self) -> None:
        """Return to the dashboard."""
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Open the selected settings subscreen."""
        try:
            if event.button.id == "global-credentials":
                self.app.push_screen(
                    GlobalCredentialsScreen(self._settings, self._navigation_mode)
                )
            elif event.button.id == "repository-credentials":
                self.app.push_screen(
                    RepositoryCredentialsScreen(self._settings, self._navigation_mode)
                )
            elif event.button.id == "repository-management":
                self.app.push_screen(
                    RepositoryManagementScreen(
                        self._settings,
                        self._settings,
                        self._navigation_mode,
                    )
                )
            elif event.button.id == "general-settings":
                self.app.push_screen(
                    GeneralSettingsScreen(
                        self._settings,
                        self._navigation_mode,
                        self._on_navigation_mode_changed,
                    )
                )
        except Exception as error:
            self.query_one("#error", Static).update(f"Settings error: {error}")
