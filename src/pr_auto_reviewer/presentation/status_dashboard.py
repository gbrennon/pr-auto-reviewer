from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.events import Key
from textual.widgets import DataTable, Footer, Header, Static

from pr_auto_reviewer.application.dtos.daemon_status_snapshot import (
    DaemonStatusSnapshot,
)
from pr_auto_reviewer.domain.value_objects.daemon_state import DaemonState
from pr_auto_reviewer.presentation.navigation import NavigationInput, NavigationMode
from pr_auto_reviewer.presentation.settings_screen import SettingsPort, SettingsScreen


class StatusDashboard(App[None]):
    """Render live daemon status and dashboard actions."""

    CSS = """
    Screen { layout: vertical; }
    #main { height: 1fr; }
    #state { border: round $primary; margin: 1; padding: 1; color: $success; text-style: bold; }
    #sort, #action-status, #last-refresh { margin: 0 1; }
    #items { height: 1fr; margin: 1; }
    #error { color: $error; margin: 0 1; }
    """
    COMMAND_PALETTE_BINDING = "ctrl+shift+p"
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
        navigation_mode: NavigationMode = NavigationMode.ARROWS,
    ) -> None:
        super().__init__()
        self._status_provider = status_provider
        self._settings = settings
        self._sort_key = self._SORT_KEYS[0]
        self._snapshot: DaemonStatusSnapshot | None = None
        self._paused = False
        self._navigation_mode = navigation_mode

    def set_navigation_mode(self, mode: NavigationMode) -> None:
        """Apply the active navigation mode to the dashboard application."""
        self._navigation_mode = mode

    def on_key(self, event: Key) -> None:
        """Move focus globally for the configured keyboard navigation mode."""
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
        yield Header(show_clock=True)
        with Vertical(id="main"):
            yield Static("Loading", id="state")
            yield Static("Sort: platform (press s to change)", id="sort")
            yield Static("Poll interval: unavailable", id="poll-interval")
            yield Static("Live refresh enabled", id="action-status")
            yield DataTable(id="items", zebra_stripes=True, cursor_type="row")
            yield Static("", id="error")
            yield Static("", id="last-refresh")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#items", DataTable)
        table.add_columns("Type", "Platform", "Repository / Role", "Details")
        self.set_interval(1.0, self.refresh_status)
        self.refresh_status()

    def action_cycle_sort(self) -> None:
        """Cycle the visible rows through supported sort keys."""
        index = self._SORT_KEYS.index(self._sort_key)
        self._sort_key = self._SORT_KEYS[(index + 1) % len(self._SORT_KEYS)]
        self._render_sort_label()
        if self._snapshot is not None:
            self._render_snapshot(self._snapshot)

    def action_refresh(self) -> None:
        """Force an immediate status refresh."""
        self.refresh_status(force=True)
        self.query_one("#action-status", Static).update("Refreshed")

    def action_toggle_pause(self) -> None:
        """Toggle automatic status refresh."""
        self._paused = not self._paused
        state = "paused" if self._paused else "live"
        self.query_one("#action-status", Static).update(
            f"Auto-refresh {state} (r to refresh)"
        )

    def action_toggle_settings(self) -> None:
        """Open the dedicated settings screen."""
        if self._settings is None:
            self.query_one("#action-status", Static).update("Settings unavailable")
            return
        self.push_screen(
            SettingsScreen(
                self._settings,
                self._navigation_mode,
                on_navigation_mode_changed=self.set_navigation_mode,
            )
        )

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
        runtime_status = snapshot.runtime_status
        poll_interval_text = (
            f"Poll interval: {runtime_status.poll_interval_seconds}s"
            if runtime_status is not None
            else "Poll interval: unavailable"
        )
        self.query_one("#poll-interval", Static).update(poll_interval_text)
        self._update_items_table(self._sorted_rows(snapshot))
        self.query_one("#error", Static).update(
            snapshot.runtime_status.last_error
            if snapshot.runtime_status and snapshot.runtime_status.last_error
            else ""
        )
        self._update_refresh_time()

    def _update_items_table(self, rows: list[tuple[str, str, str, str]]) -> None:
        table = self.query_one("#items", DataTable)
        keyed_rows = [(self._row_key(row), row) for row in rows]
        current_keys = list(table.rows)
        cursor_row = table.cursor_row
        cursor_column = table.cursor_column
        cursor_key = (
            current_keys[cursor_row]
            if 0 <= cursor_row < len(current_keys)
            else None
        )
        desired_keys = [key for key, _row in keyed_rows]
        if current_keys == desired_keys:
            column_keys = list(table.columns)
            for key, row in keyed_rows:
                existing = table.get_row(key)
                for column, value in enumerate(row):
                    if existing[column] != value:
                        table.update_cell(key, column_keys[column], value)
            return
        table.clear()
        for key, row in keyed_rows:
            table.add_row(*row, key=key)
        if not desired_keys:
            return
        target_row = (
            desired_keys.index(cursor_key)
            if cursor_key in desired_keys
            else min(cursor_row, len(desired_keys) - 1)
        )
        table.move_cursor(
            row=target_row,
            column=min(cursor_column, len(keyed_rows[0][1]) - 1),
        )

    @staticmethod
    def _row_key(row: tuple[str, str, str, str]) -> str:
        identity = row if row[0] == "capability" else row[:3]
        return "|".join(identity)

    def _render_sort_label(self) -> None:
        self.query_one("#sort", Static).update(
            f"Sort: {self._sort_key} (press s to change)"
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
        if status.state is DaemonState.ERROR or status.last_error:
            return "ERROR / RETRYING"
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
        repositories = tuple(dict.fromkeys(snapshot.allowed_repositories))
        rows = [
            ("repository", *self._repository_parts(repository), "allowed")
            for repository in repositories
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
