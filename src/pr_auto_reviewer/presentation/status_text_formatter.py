from __future__ import annotations

import math
import time

from pr_auto_reviewer.application.dtos.daemon_status_snapshot import (
    DaemonStatusSnapshot,
)
from pr_auto_reviewer.domain.entities.api_access_capability import (
    ApiAccessCapability,
)
from pr_auto_reviewer.domain.value_objects.active_review_progress import (
    ActiveReviewProgress,
)
from pr_auto_reviewer.domain.value_objects.daemon_runtime_status import (
    DaemonRuntimeStatus,
)
from pr_auto_reviewer.domain.value_objects.daemon_state import DaemonState


class StatusTextFormatter:
    """Render a daemon status snapshot as plain terminal text."""

    def format(self, snapshot: DaemonStatusSnapshot) -> str:
        """Return the human-readable status summary for a snapshot."""
        status = snapshot.runtime_status
        if status is None:
            return self._format_unknown(snapshot)
        if not snapshot.daemon_alive:
            return self._format_stopped(status, snapshot)
        sections = [
            self._format_header(status),
            self._format_state_body(status),
            self._format_allowed_repos(status, snapshot),
            self._format_capabilities(snapshot.capabilities),
        ]
        if status.last_error:
            sections.append(f"Last Error: {status.last_error}")
        return "\n\n".join(sections)

    def _format_unknown(self, snapshot: DaemonStatusSnapshot) -> str:
        repos = self._format_allowed_repos(None, snapshot)
        return (
            "PR Auto-Reviewer Status\n"
            "=======================\n"
            "Daemon: STOPPED (no status file found)\n\n"
            f"{repos}\n\n"
            f"{self._format_capabilities(snapshot.capabilities)}"
        )

    def _format_stopped(
        self, status: DaemonRuntimeStatus, snapshot: DaemonStatusSnapshot,
    ) -> str:
        repos = self._format_allowed_repos(status, snapshot)
        return (
            "PR Auto-Reviewer Status\n"
            "=======================\n"
            f"Daemon: STOPPED (PID {status.pid} is not running)\n"
            f"Last active state: {status.state.value.upper()} (cycle {status.current_cycle})\n\n"
            f"{repos}\n\n"
            f"{self._format_capabilities(snapshot.capabilities)}"
        )

    def _format_header(self, status: DaemonRuntimeStatus) -> str:
        mode = "daemon" if status.daemon_mode else "one-shot"
        return (
            "PR Auto-Reviewer Status\n"
            "=======================\n"
            f"Daemon: RUNNING (PID {status.pid}) | Mode: {mode} | Cycle: {status.current_cycle}"
        )

    def _format_state_body(self, status: DaemonRuntimeStatus) -> str:
        if status.state == DaemonState.ERROR or status.last_error:
            return self._format_error_state(status)
        if status.state == DaemonState.REVIEWING and status.current_review:
            return self._format_active_review(status.current_review)
        return self._format_idle_state(status)

    def _format_error_state(self, status: DaemonRuntimeStatus) -> str:
        return self._format_poll_state(status, "ERROR / RETRYING")

    def _format_idle_state(self, status: DaemonRuntimeStatus) -> str:
        return self._format_poll_state(status, "IDLE / WAITING")

    @staticmethod
    def _format_poll_state(status: DaemonRuntimeStatus, label: str) -> str:
        next_info = f" | Next cycle at: {status.next_cycle_at}" if status.next_cycle_at else ""
        return (
            f"Status: {label}\n"
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

    def _format_capabilities(
        self, capabilities: tuple[ApiAccessCapability, ...],
    ) -> str:
        if not capabilities:
            return "API Access Capabilities: (none recorded)"
        grouped = self._group_capabilities(capabilities)
        now = time.time()
        lines = ["API Access Capabilities"]
        lines.extend(
            line
            for platform in sorted(grouped)
            for line in self._format_capability_platform(
                platform, grouped[platform], now
            )
        )
        return "\n".join(lines)

    @staticmethod
    def _group_capabilities(
        capabilities: tuple[ApiAccessCapability, ...],
    ) -> dict[str, dict[tuple[str, str], list[ApiAccessCapability]]]:
        grouped: dict[
            str, dict[tuple[str, str], list[ApiAccessCapability]]
        ] = {}
        for capability in capabilities:
            grouped.setdefault(capability.platform, {}).setdefault(
                (capability.role, capability.source_name), []
            ).append(capability)
        return grouped

    def _format_capability_platform(
        self,
        platform: str,
        capabilities: dict[tuple[str, str], list[ApiAccessCapability]],
        now: float,
    ) -> list[str]:
        lines = [f"  - {platform}:"]
        for role, source_name in sorted(capabilities):
            lines.extend(
                self._format_capability_entries(
                    role, source_name, capabilities[(role, source_name)], now
                )
            )
        return lines

    def _format_capability_entries(
        self,
        role: str,
        source_name: str,
        entries: list[ApiAccessCapability],
        now: float,
    ) -> list[str]:
        state = self._capability_state(entries, now)
        suffix = f": {state}" if state else ":"
        lines = [f"    - {role} / {source_name}{suffix}"]
        lines.extend(
            f"      - {entry.scope or 'all scopes'}"
            for entry in sorted(entries, key=lambda item: item.scope)
        )
        return lines

    @staticmethod
    def _capability_state(
        capabilities: list[ApiAccessCapability], now: float,
    ) -> str:
        suspended = next(
            (
                capability.suspension
                for capability in capabilities
                if capability.suspension is not None
                and capability.suspension.is_active(now)
            ),
            None,
        )
        if suspended is None:
            return ""
        remaining = StatusTextFormatter._format_remaining(
            suspended.remaining_seconds(now)
        )
        return f"suspended ({remaining} remaining)"

    @staticmethod
    def _format_remaining(seconds: int) -> str:
        minutes = max(1, math.ceil(seconds / 60))
        hours, remaining_minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}h {remaining_minutes:02d}m"
        return f"{minutes}m"

    def _format_allowed_repos(
        self, status: DaemonRuntimeStatus | None, snapshot: DaemonStatusSnapshot,
    ) -> str:
        repos = self._select_allowed_repositories(status, snapshot)
        if not repos:
            return "Allowed Repositories: (all repositories permitted)"
        grouped, display_organizations = self._group_repositories(repos)
        repository_count = self._count_repositories(grouped)
        lines = [f"Allowed Repositories ({repository_count}):"]
        lines.extend(
            line
            for platform in sorted(grouped)
            for line in self._format_repository_platform(
                platform, grouped[platform], display_organizations
            )
        )
        return "\n".join(lines)

    @staticmethod
    def _count_repositories(
        grouped: dict[str, dict[str, dict[str, str]]],
    ) -> int:
        return sum(
            len(repositories)
            for organizations in grouped.values()
            for repositories in organizations.values()
        )

    @staticmethod
    def _select_allowed_repositories(
        status: DaemonRuntimeStatus | None, snapshot: DaemonStatusSnapshot,
    ) -> tuple[str, ...]:
        return (
            status.allowed_repositories
            if status and status.allowed_repositories
            else snapshot.allowed_repositories
        )

    def _group_repositories(
        self, repos: tuple[str, ...],
    ) -> tuple[dict[str, dict[str, dict[str, str]]], dict[tuple[str, str], str]]:
        grouped: dict[str, dict[str, dict[str, str]]] = {}
        display_organizations: dict[tuple[str, str], str] = {}
        for entry in repos:
            platform, repository = self._split_platform(entry)
            organization, name = self._split_repository(repository)
            platform = self._normalize_platform(platform)
            organization_key = organization.casefold()
            organizations = grouped.setdefault(platform, {})
            repositories = organizations.setdefault(organization_key, {})
            repositories.setdefault(name.casefold(), name)
            display_organizations.setdefault(
                (platform, organization_key), organization
            )
        return grouped, display_organizations

    def _format_repository_platform(
        self,
        platform: str,
        organizations: dict[str, dict[str, str]],
        display_organizations: dict[tuple[str, str], str],
    ) -> list[str]:
        lines = [f"  - {platform}:"]
        lines.extend(
            line
            for organization in sorted(organizations)
            for line in self._format_repository_organization(
                platform,
                organization,
                organizations[organization],
                display_organizations,
            )
        )
        return lines

    @staticmethod
    def _format_repository_organization(
        platform: str,
        organization: str,
        names: dict[str, str],
        display_organizations: dict[tuple[str, str], str],
    ) -> list[str]:
        lines = [
            f"    - {display_organizations[(platform, organization)]}:"
        ]
        lines.extend(f"      - {names[name]}" for name in sorted(names))
        return lines

    @staticmethod
    def _split_platform(entry: str) -> tuple[str, str]:
        if ":" not in entry:
            return "unscoped", entry
        platform, repository = entry.split(":", 1)
        return platform, repository

    @staticmethod
    def _split_repository(repository: str) -> tuple[str, str]:
        if "/" not in repository:
            return repository, ""
        organization, name = repository.split("/", 1)
        return organization, name

    @staticmethod
    def _normalize_platform(platform: str) -> str:
        normalized = platform.casefold()
        return "forgejo" if normalized == "codeberg" else normalized
