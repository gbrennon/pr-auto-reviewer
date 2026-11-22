from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import Button, DataTable, Footer, Header, Input, Static

from pr_auto_reviewer.application.dtos.daemon_status_snapshot import (
    DaemonStatusSnapshot,
)
from pr_auto_reviewer.domain.value_objects.daemon_state import DaemonState
from pr_auto_reviewer.presentation.cli.settings_cli import SettingsSnapshot

class SettingsPort(Protocol):
    """Presentation boundary for write-only settings management."""

    def snapshot(self) -> SettingsSnapshot:
        """Return visible settings and secret names."""

    def write(self, name: str, raw_value: str) -> None:
        """Write a setting without returning its value."""

    def unset(self, name: str) -> None:
        """Remove a setting."""

class StatusDashboard(App[None]):
    """Render live daemon status and settings actions in a terminal dashboard."""

    CSS = """
    Screen { layout: vertical; }
    #main { height: 1fr; }
    #state { border: round $primary; margin: 1; padding: 1; color: $success; text-style: bold; }
    #sort, #action-status, #last-refresh { margin: 0 1; }
    #items { height: 1fr; margin: 1; }
    #settings { display: none; border: round $accent; margin: 1; padding: 1; }
    #settings-list { height: 1fr; }
    #setting-name, #setting-value { margin: 1 0; }
    #error { color: $error; margin: 0 1; }
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("s", "cycle_sort", "Sort"),
        ("r", "refresh", "Refresh"),
        ("p", "toggle_pause", "Pause"),
        ("e", "toggle_settings", "Settings"),
    ]
    _SORT_KEYS = ("platform", "repository", "status")

    def __init__(
        self,
        status_provider: Callable[[], DaemonStatusSnapshot],
        settings: SettingsPort | None = None,
    ) -> None:
        super().__init__()
        self._status_provider = status_provider
        self._settings = settings
        self._sort_key = self._SORT_KEYS[0]
        self._snapshot: DaemonStatusSnapshot | None = None
        self._paused = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="main"):
            yield Static("Loading", id="state")
            yield Static("Sort: platform (press s to change)", id="sort")
            yield Static("Live refresh enabled", id="action-status")
            yield DataTable(id="items", zebra_stripes=True, cursor_type="row")
            with Vertical(id="settings"):
                yield Static("Settings (e to close; secrets are write-only)", id="settings-title")
                yield Static("", id="settings-list")
                yield Input(placeholder="Setting name", id="setting-name")
                yield Input(
                    placeholder="Value (never displayed after save)",
                    password=True,
                    id="setting-value",
                )
                yield Button("Save", id="save-setting", variant="primary")
                yield Button("Unset", id="unset-setting", variant="error")
            yield Static("", id="error")
            yield Static("", id="last-refresh")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#items", DataTable)
        table.add_columns("Type", "Platform", "Repository / Role", "Details")
        self.set_interval(1.0, self.refresh_status)
        self.refresh_status()

    def action_cycle_sort(self) -> None:
        """Cycle the visible rows through the supported sort keys."""
        index = self._SORT_KEYS.index(self._sort_key)
        self._sort_key = self._SORT_KEYS[(index + 1) % len(self._SORT_KEYS)]
        self._render_sort_label()
        if self._snapshot is not None:
            self._render_snapshot(self._snapshot)

    def action_refresh(self) -> None:
        """Force an immediate status refresh even when auto-refresh is paused."""
        self.refresh_status(force=True)
        self.query_one("#action-status", Static).update("Refreshed")

    def action_toggle_pause(self) -> None:
        """Toggle automatic status refresh while keeping manual refresh available."""
        self._paused = not self._paused
        state = "paused" if self._paused else "live"
        self.query_one("#action-status", Static).update(
            f"Auto-refresh {state} (r to refresh)"
        )

    def action_toggle_settings(self) -> None:
        """Toggle the write-only settings editor."""
        panel = self.query_one("#settings", Vertical)
        if self._settings is None:
            self.query_one("#action-status", Static).update("Settings unavailable")
            return
        panel.styles.display = "none" if panel.styles.display == "block" else "block"
        if panel.styles.display == "block":
            self._render_settings()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Persist or remove the setting named in the editor."""
        if self._settings is None:
            return
        name = self.query_one("#setting-name", Input).value.strip()
        if not name:
            self.query_one("#error", Static).update("Setting name is required")
            return
        try:
            if event.button.id == "save-setting":
                self._settings.write(
                    name, self.query_one("#setting-value", Input).value
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

    def refresh_status(self, force: bool = False) -> None:
        """Refresh dashboard rows from the application snapshot."""
        if self._paused and not force:
            return
        try:
            snapshot = self._status_provider()
        except Exception as error:
            self._snapshot = None
            self.query_one("#state", Static).update("ERROR")
            self.query_one("#error", Static).update(f"Error: {error}")
            self._update_refresh_time()
            return
        self._snapshot = snapshot
        self._render_snapshot(snapshot)

    def _render_snapshot(self, snapshot: DaemonStatusSnapshot) -> None:
        self.query_one("#state", Static).update(self._state_text(snapshot))
        self._render_sort_label()
        table = self.query_one("#items", DataTable)
        table.clear()
        for row in self._sorted_rows(snapshot):
            table.add_row(*row)
        self.query_one("#error", Static).update(
            snapshot.runtime_status.last_error
            if snapshot.runtime_status and snapshot.runtime_status.last_error
            else ""
        )
        self._update_refresh_time()

    def _render_sort_label(self) -> None:
        self.query_one("#sort", Static).update(
            f"Sort: {self._sort_key} (press s to change)"
        )

    def _render_settings(self) -> None:
        if self._settings is None:
            return
        snapshot = self._settings.snapshot()
        values = [f"{name} = {value}" for name, value in snapshot.values]
        values.extend(f"{name} = <write-only>" for name in snapshot.secret_names)
        self.query_one("#settings-list", Static).update(
            "\n".join(values) if values else "No settings configured"
        )

    def _update_refresh_time(self) -> None:
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

    def _sorted_rows(
        self, snapshot: DaemonStatusSnapshot,
    ) -> list[tuple[str, str, str, str]]:
        rows = self._rows(snapshot)
        sort_index = {"platform": 1, "repository": 2, "status": 0}[self._sort_key]
        return sorted(rows, key=lambda row: (row[sort_index].casefold(), row[2].casefold()))

    def _rows(self, snapshot: DaemonStatusSnapshot) -> list[tuple[str, str, str, str]]:
        status = snapshot.runtime_status
        rows = [
            ("repository", *self._repository_parts(repository), "allowed")
            for repository in snapshot.allowed_repositories
        ]
        rows.extend(
            (
                "capability",
                capability.platform,
                f"{capability.role} / {capability.source_name}",
                capability.scope or "all scopes",
            )
            for capability in snapshot.capabilities
        )
        review = status.current_review if status is not None else None
        if review is not None:
            rows.append(
                (
                    "active review",
                    *self._repository_parts(review.repository),
                    f"PR #{review.pr_number} · {review.phase_name or 'starting'} · "
                    f"turn {review.current_turn}/{review.max_turns}",
                )
            )
        return rows

    @staticmethod
    def _repository_parts(repository: str) -> tuple[str, str]:
        platform, separator, name = repository.partition(":")
        if not separator:
            return "unscoped", repository
        return platform, name
