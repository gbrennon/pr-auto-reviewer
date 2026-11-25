from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, Input, Select, Static

from pr_auto_reviewer.presentation.global_credential_port import GlobalCredentialPort
from pr_auto_reviewer.presentation.navigation import NavigationInput, NavigationMode


class GlobalCredentialsScreen(Screen[None]):
    """Set or clear one platform-global role credential."""

    CSS = """
    Screen { layout: vertical; overflow-y: auto; }
    .field-label { margin: 1 1 0 1; }
    Input, Select, Button { margin: 0 1; }
    #help, #status, #error { margin: 1; }
    #error { color: $error; }
    """
    BINDINGS = [
        Binding("q", "back", "Back", priority=True),
        Binding("escape", "back", "Back", priority=True),
    ]

    def __init__(self, settings: GlobalCredentialPort, navigation_mode: NavigationMode) -> None:
        super().__init__()
        self._settings = settings
        self._navigation_mode = navigation_mode

    def compose(self) -> ComposeResult:
        yield Static("Global credentials", id="title")
        yield Static(
            "Global credentials are fallback credentials for one platform and role.",
            id="help",
        )
        yield Static("Platform", classes="field-label")
        yield Select(
            [("GitHub", "github"), ("Forgejo", "forgejo")],
            value="github",
            id="platform",
        )
        yield Static("Role", classes="field-label")
        yield Select(
            [("Manager", "manager"), ("Reviewer", "reviewer")],
            value="manager",
            id="role",
        )
        yield Static("Token (leave blank to clear this role)", classes="field-label")
        yield NavigationInput(password=True, id="token", mode=self._navigation_mode)
        yield Button("Save global credential", id="save", variant="primary")
        yield Button("Back", id="back")
        yield Static("", id="status")
        yield Static("", id="error")

    def action_back(self) -> None:
        """Return to the settings home."""
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Save or leave the global credential screen."""
        if event.button.id == "back":
            self.action_back()
            return
        try:
            platform = str(self.query_one("#platform", Select).value)
            role = str(self.query_one("#role", Select).value)
            token = self.query_one("#token", Input).value
            self._settings.save_global_credential(platform, role, token)
            action = "cleared" if not token else "saved"
            self.query_one("#status", Static).update(
                f"Global {platform} {role} credential {action}"
            )
            self.query_one("#error", Static).update("")
        except Exception as error:
            self.query_one("#error", Static).update(f"Credential error: {error}")
