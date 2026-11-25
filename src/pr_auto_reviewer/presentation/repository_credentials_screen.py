from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, Input, Select, Static

from pr_auto_reviewer.presentation.navigation import NavigationInput, NavigationMode
from pr_auto_reviewer.presentation.repository_credential_port import RepositoryCredentialPort

class RepositoryCredentialsScreen(Screen[None]):
    """Set or clear optional full-repository role credentials."""

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

    def __init__(
        self,
        settings: RepositoryCredentialPort,
        navigation_mode: NavigationMode,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._navigation_mode = navigation_mode

    def compose(self) -> ComposeResult:
        yield Static("Repository credentials", id="title")
        yield Static(
            "Leave either role blank to use that role's global fallback. "
            "Leave both blank to clear repository-specific credentials.",
            id="help",
        )
        yield Static("Platform", classes="field-label")
        yield Select(
            [("GitHub", "github"), ("Forgejo", "forgejo")],
            value="github",
            id="platform",
        )
        yield Static("Repository owner/name", classes="field-label")
        yield NavigationInput(placeholder="owner/repository", id="repository", mode=self._navigation_mode)
        yield Static("Manager token (optional)", classes="field-label")
        yield NavigationInput(password=True, id="manager-token", mode=self._navigation_mode)
        yield Static("Reviewer token (optional)", classes="field-label")
        yield NavigationInput(password=True, id="reviewer-token", mode=self._navigation_mode)
        yield Button("Save repository credentials", id="save", variant="primary")
        yield Button("Back", id="back")
        yield Static("", id="status")
        yield Static("", id="error")

    def action_back(self) -> None:
        """Return to the settings home."""
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Save or leave the repository credential screen."""
        if event.button.id == "back":
            self.action_back()
            return
        try:
            platform = str(self.query_one("#platform", Select).value)
            repository = self.query_one("#repository", Input).value.strip()
            if not repository or "/" not in repository:
                raise ValueError("repository owner/name is required")
            manager = self.query_one("#manager-token", Input).value
            reviewer = self.query_one("#reviewer-token", Input).value
            self._settings.save_repository_credentials(
                f"{platform}:{repository}", manager, reviewer
            )
            action = "cleared" if not manager and not reviewer else "saved"
            self.query_one("#status", Static).update(
                f"Repository credentials {action} for {platform}:{repository}"
            )
            self.query_one("#error", Static).update("")
        except Exception as error:
            self.query_one("#error", Static).update(f"Credential error: {error}")
