from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Static

from pr_auto_reviewer.application.dtos.daemon_status_snapshot import (
    DaemonStatusSnapshot,
)
from pr_auto_reviewer.domain.value_objects.daemon_state import DaemonState

class StatusDashboard(App[None]):
    """Render live daemon status in a terminal dashboard."""

    CSS = """
    Screen { layout: vertical; }
    #main { height: 1fr; }
    .panel { border: round $primary; margin: 1; padding: 1; width: 1fr; }
    #state { color: $success; text-style: bold; }
    #error { color: $error; }
    """
    BINDINGS = [("q", "quit", "Quit")]

    def __init__(
        self, status_provider: Callable[[], DaemonStatusSnapshot],
    ) -> None:
        super().__init__()
        self._status_provider = status_provider

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="main"):
            with Horizontal():
                yield Static("Loading", id="state", classes="panel")
                yield Static("", id="review", classes="panel")
            with Horizontal():
                yield Static("", id="repositories", classes="panel")
                yield Static("", id="capabilities", classes="panel")
            yield Static("", id="error", classes="panel")
            yield Static("", id="last-refresh")
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(1.0, self.refresh_status)
        self.refresh_status()

    def refresh_status(self) -> None:
        """Refresh every dashboard panel from the application snapshot."""
        try:
            snapshot = self._status_provider()
        except Exception as error:
            self.query_one("#state", Static).update("ERROR")
            self.query_one("#review", Static).update("")
            self.query_one("#error", Static).update(f"Error: {error}")
            self.query_one("#last-refresh", Static).update(
                f"Last refresh: {datetime.now().astimezone().isoformat(timespec='seconds')}"
            )
            return

        self.query_one("#state", Static).update(self._state_text(snapshot))
        self.query_one("#review", Static).update(self._review_text(snapshot))
        self.query_one("#repositories", Static).update(
            self._repositories_text(snapshot)
        )
        self.query_one("#capabilities", Static).update(
            self._capabilities_text(snapshot)
        )
        self.query_one("#error", Static).update(
            snapshot.runtime_status.last_error
            if snapshot.runtime_status and snapshot.runtime_status.last_error
            else ""
        )
        self.query_one("#last-refresh", Static).update(
            f"Last refresh: {datetime.now().astimezone().isoformat(timespec='seconds')}"
        )

    def _state_text(self, snapshot: DaemonStatusSnapshot) -> str:
        status = snapshot.runtime_status
        if status is None:
            return "STOPPED (no status file found)"
        if not snapshot.daemon_alive:
            return f"STOPPED (PID {status.pid} is not running)"
        if status.state is DaemonState.REVIEWING:
            return "REVIEWING"
        return "IDLE / WAITING"

    def _review_text(self, snapshot: DaemonStatusSnapshot) -> str:
        status = snapshot.runtime_status
        review = status.current_review if status is not None else None
        if review is None:
            return "Active Review: none"
        return (
            f"Active Review: {review.repository} #{review.pr_number}\n"
            f"{review.pr_title}\n"
            f"Phase: {review.phase_name}\n"
            f"Progress: Turn {review.current_turn}/{review.max_turns}\n"
            f"Action: {review.last_tool_call or 'initializing'}"
        )

    def _repositories_text(self, snapshot: DaemonStatusSnapshot) -> str:
        if not snapshot.allowed_repositories:
            return "Allowed Repositories: all repositories permitted"
        entries = "\n".join(f"- {repository}" for repository in snapshot.allowed_repositories)
        return f"Allowed Repositories\n{entries}"

    def _capabilities_text(self, snapshot: DaemonStatusSnapshot) -> str:
        if not snapshot.capabilities:
            return "API Access Capabilities: none recorded"
        entries = "\n".join(
            f"- {capability.platform} / {capability.role} / "
            f"{capability.scope or 'all scopes'}"
            for capability in snapshot.capabilities
        )
        return f"API Access Capabilities\n{entries}"
