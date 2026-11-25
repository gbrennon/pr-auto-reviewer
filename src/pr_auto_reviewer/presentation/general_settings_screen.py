from __future__ import annotations

from collections.abc import Callable

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, Input, Select, Static

from pr_auto_reviewer.presentation.general_settings_port import GeneralSettingsPort
from pr_auto_reviewer.presentation.navigation import NavigationInput, NavigationMode

class GeneralSettingsScreen(Screen[None]):
    """Edit non-credential settings with explicit labels."""

    CSS = """
    Screen { layout: vertical; overflow-y: auto; }
    .field-label { margin: 1 1 0 1; }
    Input, Select, Button { margin: 0 1; }
    #settings-list { height: auto; border: round $accent; margin: 1; padding: 1; }
    #action-status, #error { margin: 1; }
    #error { color: $error; }
    """
    BINDINGS = [
        Binding("q", "back", "Back", priority=True),
        Binding("escape", "back", "Back", priority=True),
    ]

    def __init__(
        self,
        settings: GeneralSettingsPort,
        navigation_mode: NavigationMode,
        on_navigation_mode_changed: Callable[[NavigationMode], None] | None,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._navigation_mode = navigation_mode
        self._on_navigation_mode_changed = on_navigation_mode_changed

    def compose(self) -> ComposeResult:
        yield Static("General settings", id="settings-title")
        yield Static("Current settings", classes="field-label")
        yield Static("", id="settings-list")
        yield Static("Navigation mode", classes="field-label")
        yield Select(
            [(mode.value.title(), mode.value) for mode in NavigationMode],
            value=self._navigation_mode.value,
            id="navigation-mode",
        )
        yield Static("Setting", classes="field-label")
        yield Select([], id="setting-key")
        yield Static("Value (write-only for secrets)", classes="field-label")
        yield NavigationInput(id="setting-value", password=True, mode=self._navigation_mode)
        yield Button("Save setting", id="save-setting", variant="primary")
        yield Button("Remove setting", id="unset-setting", variant="error")
        yield Button("Back", id="back")
        yield Static("", id="action-status")
        yield Static("", id="error")

    def on_mount(self) -> None:
        """Render current general settings."""
        self._render_settings()

    def action_back(self) -> None:
        """Return to the settings home."""
        self.app.pop_screen()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Persist navigation changes and load the selected setting."""
        if event.select.id == "navigation-mode":
            mode = NavigationMode.parse(str(event.value))
            if self._on_navigation_mode_changed is not None:
                self._on_navigation_mode_changed(mode)
            self._settings.write("TUI_NAVIGATION_MODE", mode.value)
            self.query_one("#action-status", Static).update(
                f"Navigation mode: {mode.value}"
            )
            return
        if event.select.id == "setting-key":
            self._update_selected_value(str(event.value))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Save, remove, or leave the general settings screen."""
        if event.button.id == "back":
            self.action_back()
            return
        try:
            name = str(self.query_one("#setting-key", Select).value)
            if not name or name == str(Select.BLANK):
                self.query_one("#error", Static).update("Select a setting")
                return
            if event.button.id == "save-setting":
                self._settings.write(
                    name,
                    self.query_one("#setting-value", Input).value,
                )
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
        keys = [name for name, _value in snapshot.values]
        keys.extend(name for name in snapshot.secret_names if name not in keys)
        selector = self.query_one("#setting-key", Select)
        current = str(selector.value)
        selector.set_options([(name, name) for name in keys])
        if keys and current not in keys:
            selector.value = keys[0]
        self._update_selected_value(str(selector.value))

    def _update_selected_value(self, name: str) -> None:
        """Load a selected non-secret value without exposing secret values."""
        snapshot = self._settings.snapshot()
        values = dict(snapshot.values)
        value = "" if name in snapshot.secret_names else values.get(name, "")
        self.query_one("#setting-value", Input).value = value
