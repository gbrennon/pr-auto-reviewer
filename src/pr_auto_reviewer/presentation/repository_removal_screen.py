from __future__ import annotations

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Button, Select, Static

from pr_auto_reviewer.presentation.repository_management_port import (
    RepositoryManagementPort,
)


class RepositoryRemovalScreen(Screen[None]):
    """Select a registered repository before removing it."""

    CSS = """
    Screen { layout: vertical; overflow-y: auto; }
    .field-label { margin: 1 1 0 1; }
    Select, Button { margin: 0 1; }
    #help, #status, #error { margin: 1; }
    #error { color: $error; }
    """
    BINDINGS = [
        Binding("q", "back", "Back", priority=True),
        Binding("escape", "back", "Back", priority=True),
    ]

    def __init__(self, settings: RepositoryManagementPort) -> None:
        super().__init__()
        self._settings = settings

    def compose(self) -> ComposeResult:
        yield Static("Remove repository", id="title")
        yield Static(
            "Select a registered repository to remove it from the allow list.",
            id="help",
        )
        yield Static("Repository", classes="field-label")
        yield Select([], id="repository")
        yield Button("Remove repository", id="remove", variant="error")
        yield Button("Back", id="back")
        yield Static("", id="status")
        yield Static("", id="error")

    def on_mount(self) -> None:
        """Load registered repositories into the selector."""
        self._render_repositories()

    def action_back(self) -> None:
        """Return to repository management."""
        self.app.pop_screen()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Remove the selected repository or leave the screen."""
        if event.button.id == "back":
            self.action_back()
            return
        try:
            repository = self._selected_repository()
            self._settings.remove_repository(repository)
            self._render_repositories()
            self.query_one("#status", Static).update(f"Removed {repository}")
            self.query_one("#error", Static).update("")
        except Exception as error:
            self.query_one("#error", Static).update(f"Repository error: {error}")

    def _selected_repository(self) -> str:
        value = self.query_one("#repository", Select).value
        if value is Select.BLANK or not value:
            raise ValueError("select a repository")
        return str(value)

    def _render_repositories(self) -> None:
        repositories = [
            status.repository for status in self._settings.list_repositories()
        ]
        selector = self.query_one("#repository", Select)
        selector.set_options([(repository, repository) for repository in repositories])
        if repositories:
            selector.value = repositories[0]
        else:
            selector.value = Select.BLANK
            self.query_one("#status", Static).update("No repositories registered")
