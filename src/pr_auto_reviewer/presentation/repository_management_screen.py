from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, Input, Select, Static

from pr_auto_reviewer.presentation.navigation import NavigationInput, NavigationMode
from pr_auto_reviewer.presentation.repository_credential_port import RepositoryCredentialPort
from pr_auto_reviewer.presentation.repository_management_port import RepositoryManagementPort
from pr_auto_reviewer.presentation.repository_credentials_screen import RepositoryCredentialsScreen


class RepositoryManagementScreen(Screen[None]):
    """Register repositories and inspect credential fallback sources."""

    CSS = """
    Screen { layout: vertical; overflow-y: auto; }
    .field-label { margin: 1 1 0 1; }
    Input, Select, Button { margin: 0 1; }
    #repository-list { height: auto; border: round $accent; margin: 1; padding: 1; }
    #status, #error { margin: 1; }
    #error { color: $error; }
    """
    BINDINGS = [
        Binding("q", "back", "Back", priority=True),
        Binding("escape", "back", "Back", priority=True),
    ]

    def __init__(
        self,
        settings: RepositoryManagementPort,
        credential_settings: RepositoryCredentialPort,
        navigation_mode: NavigationMode,
    ) -> None:
        super().__init__()
        self._settings = settings
        self._credential_settings = credential_settings
        self._navigation_mode = navigation_mode

    def compose(self) -> ComposeResult:
        yield Static("Repository management", id="title")
        yield Static("Registered repositories", classes="field-label")
        yield Static("", id="repository-list")
        yield Static("Platform", classes="field-label")
        yield Select(
            [("GitHub", "github"), ("Forgejo", "forgejo")],
            value="github",
            id="platform",
        )
        yield Static("Repository owner/name", classes="field-label")
        yield NavigationInput(placeholder="owner/repository", id="repository", mode=self._navigation_mode)
        yield Button("Register repository", id="register", variant="primary")
        yield Button("Remove repository", id="remove", variant="error")
        yield Button("Edit repository credentials", id="edit-credentials")
        yield Button("Back", id="back")
        yield Static("", id="status")
        yield Static("", id="error")

    def on_mount(self) -> None:
        """Render registered repositories without credential values."""
        self._render_repositories()

    def action_back(self) -> None:
        """Return to the settings home."""
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Register, remove, edit, or leave repository management."""
        if event.button.id == "back":
            self.action_back()
            return
        try:
            if event.button.id == "edit-credentials":
                self.app.push_screen(
                    RepositoryCredentialsScreen(
                        self._credential_settings,
                        self._navigation_mode,
                    )
                )
                return
            repository = self._repository()
            if event.button.id == "register":
                self._settings.add_repository(repository)
                message = f"Registered {repository}"
            else:
                self._settings.remove_repository(repository)
                message = f"Removed {repository}"
            self._render_repositories()
            self.query_one("#status", Static).update(message)
            self.query_one("#error", Static).update("")
        except Exception as error:
            self.query_one("#error", Static).update(f"Repository error: {error}")

    def _repository(self) -> str:
        platform = str(self.query_one("#platform", Select).value)
        repository = self.query_one("#repository", Input).value.strip()
        if not repository or "/" not in repository:
            raise ValueError("repository owner/name is required")
        return f"{platform}:{repository}"

    def _render_repositories(self) -> None:
        rows = []
        for status in self._settings.list_repositories():
            manager = self._credential_line("manager", status.manager_source, status.manager_error)
            reviewer = self._credential_line("reviewer", status.reviewer_source, status.reviewer_error)
            rows.append(f"{status.repository}\n{manager}\n{reviewer}")
        self.query_one("#repository-list", Static).update(
            "\n\n".join(rows) if rows else "No repositories registered"
        )

    def _credential_line(self, role: str, source: str, error: str) -> str:
        if source != "error":
            return f"  {role}: {source}"
        detail = error or "credential status could not be loaded"
        return f"  {role}: error — {detail}"
