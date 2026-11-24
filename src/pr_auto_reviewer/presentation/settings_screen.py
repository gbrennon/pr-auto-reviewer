from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

from textual.app import ComposeResult
from textual.binding import Binding
from textual.events import Key
from textual.screen import Screen
from textual.widgets import Button, Input, Select, Static

from pr_auto_reviewer.presentation.cli.settings_cli import SettingsSnapshot
from pr_auto_reviewer.presentation.navigation import (
    NavigationButton,
    NavigationInput,
    NavigationMode,
)


class SettingsPort(Protocol):
    """Presentation boundary for write-only settings management."""

    def snapshot(self) -> SettingsSnapshot:
        """Return visible settings and secret names."""

    def write(self, name: str, raw_value: str) -> None:
        """Write a setting without returning its value."""

    def unset(self, name: str) -> None:
        """Remove a setting."""

    def add_repository(self, repository: str, manager_token: str, reviewer_token: str) -> None:
        """Allow a repository with role-specific write-only tokens."""

    def remove_repository(self, repository: str) -> None:
        """Remove a repository from the allow list."""


class SettingsScreen(Screen[None]):
    """Full-screen write-only settings editor."""

    CSS = """
    Screen { layout: vertical; overflow-y: auto; }
    #settings-list { height: auto; border: round $accent; margin: 1; padding: 1; }
    #setting-name, #setting-value, #repository, #manager-token, #reviewer-token { margin: 1 0; }
    #error { color: $error; margin: 0 1; }
    #action-status { margin: 0 1; }
    """
    BINDINGS = [
        Binding("q", "back", "Back", priority=True),
        Binding("escape", "back", "Back", priority=True),
    ]

    def __init__(
        self,
        settings: SettingsPort,
        navigation_mode: NavigationMode,
        on_navigation_mode_changed: Callable[[NavigationMode], None] | None = None,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._navigation_mode = navigation_mode
        self._on_navigation_mode_changed = on_navigation_mode_changed

    def on_key(self, event: Key) -> None:
        """Move focus across every settings control in the configured mode."""
        focused = self.focused
        if isinstance(focused, NavigationInput) and focused.is_vim_insert_mode:
            return
        if self._navigation_mode is NavigationMode.VIM:
            if event.key == "j":
                self.screen.focus_next()
            elif event.key == "k":
                self.screen.focus_previous()
            else:
                return
        elif self._navigation_mode is NavigationMode.EMACS:
            if event.key == "ctrl+n":
                self.screen.focus_next()
            elif event.key == "ctrl+p":
                self.screen.focus_previous()
            else:
                return
        else:
            return
        event.stop()
        event.prevent_default()

    def compose(self) -> ComposeResult:
        yield Static("Settings (q or Escape to return; secrets are write-only)", id="settings-title")
        yield Static("", id="settings-list")
        yield Select(
            [(mode.value.title(), mode.value) for mode in NavigationMode],
            value=self._navigation_mode.value,
            id="navigation-mode",
        )
        yield NavigationInput(
            placeholder="Setting name", id="setting-name", mode=self._navigation_mode,
        )
        yield NavigationInput(
            placeholder="Repository platform:owner/name", id="repository", mode=self._navigation_mode,
        )
        yield NavigationInput(
            placeholder="Manager token (write-only)", password=True, id="manager-token",
            mode=self._navigation_mode,
        )
        yield NavigationInput(
            placeholder="Reviewer token (write-only)", password=True, id="reviewer-token",
            mode=self._navigation_mode,
        )
        yield NavigationButton(
            "Add repository", id="add-repository", variant="primary", mode=self._navigation_mode,
        )
        yield NavigationButton(
            "Remove repository", id="remove-repository", variant="error", mode=self._navigation_mode,
        )
        yield NavigationInput(
            placeholder="Value (never displayed after save)", password=True,
            id="setting-value", mode=self._navigation_mode,
        )
        yield NavigationButton(
            "Save", id="save-setting", variant="primary", mode=self._navigation_mode,
        )
        yield NavigationButton(
            "Unset", id="unset-setting", variant="error", mode=self._navigation_mode,
        )
        yield Static("", id="action-status")
        yield Static("", id="error")

    def on_mount(self) -> None:
        """Render persisted settings when the screen opens."""
        self._render_settings()

    def action_back(self) -> None:
        """Return to the live status dashboard."""
        self.app.pop_screen()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Persist and apply a newly selected navigation mode."""
        if event.select.id != "navigation-mode":
            return
        mode = NavigationMode.parse(str(event.value))
        if mode is self._navigation_mode:
            return
        self._navigation_mode = mode
        widgets = [*self.query(NavigationInput), *self.query(NavigationButton)]
        for widget in widgets:
            widget.set_navigation_mode(mode)
        if self._on_navigation_mode_changed is not None:
            self._on_navigation_mode_changed(mode)
        try:
            self._settings.write("TUI_NAVIGATION_MODE", mode.value)
            self.query_one("#action-status", Static).update(
                f"Navigation mode: {mode.value}"
            )
            self.query_one("#error", Static).update("")
        except Exception as error:
            self.query_one("#error", Static).update(f"Settings error: {error}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Persist or remove a setting or repository."""
        repository = self.query_one("#repository", Input).value.strip()
        try:
            if event.button.id == "add-repository":
                self._settings.add_repository(
                    repository,
                    self.query_one("#manager-token", Input).value,
                    self.query_one("#reviewer-token", Input).value,
                )
                message = f"Added {repository}"
            elif event.button.id == "remove-repository":
                self._settings.remove_repository(repository)
                message = f"Removed {repository}"
            else:
                name = self.query_one("#setting-name", Input).value.strip()
                if not name:
                    self.query_one("#error", Static).update("Setting name is required")
                    return
                if event.button.id == "save-setting":
                    self._settings.write(name, self.query_one("#setting-value", Input).value)
                    message = f"Updated {name}"
                else:
                    self._settings.unset(name)
                    message = f"Removed {name}"
            self._render_settings()
            self.query_one("#action-status", Static).update(message)
            self.query_one("#error", Static).update("")
        except Exception as error:
            self.query_one("#error", Static).update(f"Settings error: {error}")

    def _render_settings(self) -> None:
        snapshot = self._settings.snapshot()
        values = [f"{name} = {value}" for name, value in snapshot.values]
        values.extend(f"{name} = <write-only>" for name in snapshot.secret_names)
        if snapshot.secret_error:
            values.append("Secret storage unavailable: " + snapshot.secret_error)
        self.query_one("#settings-list", Static).update(
            "\n".join(values) if values else "No settings configured"
        )
