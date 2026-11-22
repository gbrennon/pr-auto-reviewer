from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Vertical
from textual.widgets import DataTable, Footer, Header, Static

from pr_auto_reviewer.application.dtos.daemon_status_snapshot import (
    DaemonStatusSnapshot,
)
from pr_auto_reviewer.domain.value_objects.daemon_state import DaemonState

class StatusDashboard(App[None]):
    """Render live daemon status in a grouped, sortable terminal dashboard."""

    CSS = """
    Screen { layout: vertical; }
    #main { height: 1fr; }
    #state { border: round $primary; margin: 1; padding: 1; color: $success; text-style: bold; }
    #sort { margin: 0 1; }
    #items { height: 1fr; margin: 1; }
    #error { color: $error; margin: 0 1; }
    #last-refresh { margin: 0 1; }
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("s", "cycle_sort", "Sort"),
    ]
    _SORT_KEYS = ("platform", "repository", "status")

    def __init__(
        self, status_provider: Callable[[], DaemonStatusSnapshot],
    ) -> None:
        super().__init__()
        self._status_provider = status_provider
        self._sort_key = self._SORT_KEYS[0]
        self._snapshot: DaemonStatusSnapshot | None = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="main"):
            yield Static("Loading", id="state")
            yield Static("Sort: platform (press s to change)", id="sort")
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
        """Cycle the visible rows through the supported sort keys."""
        index = self._SORT_KEYS.index(self._sort_key)
        self._sort_key = self._SORT_KEYS[(index + 1) % len(self._SORT_KEYS)]
        self.query_one("#sort", Static).update(
            f"Sort: {self._sort_key} (press s to change)"
        )
        if self._snapshot is not None:
            self._render_snapshot(self._snapshot)

    def refresh_status(self) -> None:
        """Refresh dashboard rows from the application snapshot."""
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
        self.query_one("#sort", Static).update(
            f"Sort: {self._sort_key} (press s to change)"
        )
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
