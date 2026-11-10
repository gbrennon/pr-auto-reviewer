"""ShowStatusService — compiles real-time daemon state into human-readable output."""

from __future__ import annotations

from collections.abc import Callable

from pr_auto_reviewer.application.ports.outbound.daemon_runtime_state_port import (
    DaemonRuntimeStatePort,
)
from pr_auto_reviewer.domain.value_objects.active_review_progress import (
    ActiveReviewProgress,
)
from pr_auto_reviewer.domain.value_objects.daemon_runtime_status import (
    DaemonRuntimeStatus,
)
from pr_auto_reviewer.domain.value_objects.daemon_state import DaemonState


class ShowStatusService:
    """Formats human-readable runtime telemetry from the daemon status store."""

    def __init__(
        self,
        runtime_state: DaemonRuntimeStatePort,
        process_checker: Callable[[int], bool],
        allowed_repositories: tuple[str, ...],
    ) -> None:
        self._runtime_state = runtime_state
        self._process_checker = process_checker
        self._allowed_repositories = allowed_repositories

    def show_status(self) -> str:
        """Return formatted summary of current daemon runtime status."""
        status = self._runtime_state.read_status()
        if status is None:
            return self._format_unknown()

        is_alive = self._process_checker(status.pid)
        if not is_alive:
            return self._format_stopped(status)

        sections = [
            self._format_header(status),
            self._format_state_body(status),
            self._format_allowed_repos(status),
        ]
        if status.last_error:
            sections.append(f"Last Error: {status.last_error}")
        return "\n\n".join(sections)

    def _format_unknown(self) -> str:
        repos = self._format_allowed_repos(None)
        return (
            "PR Auto-Reviewer Status\n"
            "=======================\n"
            "Daemon: STOPPED (no status file found)\n\n"
            f"{repos}"
        )

    def _format_stopped(self, status: DaemonRuntimeStatus) -> str:
        repos = self._format_allowed_repos(status)
        return (
            "PR Auto-Reviewer Status\n"
            "=======================\n"
            f"Daemon: STOPPED (PID {status.pid} is not running)\n"
            f"Last active state: {status.state.value.upper()} (cycle {status.current_cycle})\n\n"
            f"{repos}"
        )

    def _format_header(self, status: DaemonRuntimeStatus) -> str:
        mode = "daemon" if status.daemon_mode else "one-shot"
        return (
            "PR Auto-Reviewer Status\n"
            "=======================\n"
            f"Daemon: RUNNING (PID {status.pid}) | Mode: {mode} | Cycle: {status.current_cycle}"
        )

    def _format_state_body(self, status: DaemonRuntimeStatus) -> str:
        if status.state == DaemonState.REVIEWING and status.current_review:
            return self._format_active_review(status.current_review)
        next_info = f" | Next cycle at: {status.next_cycle_at}" if status.next_cycle_at else ""
        return (
            f"Status: IDLE / WAITING\n"
            f"Poll interval: {status.poll_interval_seconds}s{next_info}"
        )

    def _format_active_review(self, review: ActiveReviewProgress) -> str:
        phase_info = (
            f"Phase {review.phase_index}/{review.total_phases}"
            if review.total_phases
            else "In progress"
        )
        action = (
            f"{review.last_tool_call}({review.last_tool_args})"
            if review.last_tool_call
            else "initializing"
        )
        return (
            f"Status: REVIEWING ({phase_info})\n"
            f"Active Review: {review.repository} #{review.pr_number} "
            f"— {review.pr_title} ({review.head_sha[:7]})\n"
            f"Phase: {review.phase_name} [{review.subagent_role or 'agent'}]\n"
            f"Progress: Turn {review.current_turn}/{review.max_turns} | Action: {action}"
        )

    def _format_allowed_repos(self, status: DaemonRuntimeStatus | None) -> str:
        repos = (
            status.allowed_repositories
            if status and status.allowed_repositories
            else self._allowed_repositories
        )
        if not repos:
            return "Allowed Repositories: (all repositories permitted)"
        lines = "\n".join(f"  - {repo}" for repo in repos)
        return f"Allowed Repositories ({len(repos)}):\n{lines}"
