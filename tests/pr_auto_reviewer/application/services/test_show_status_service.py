from __future__ import annotations

import time
from unittest.mock import MagicMock

from pr_auto_reviewer.application.services.show_status_service import (
    ShowStatusService,
)
from pr_auto_reviewer.domain.entities.api_access_capability import (
    ApiAccessCapability,
)
from pr_auto_reviewer.domain.value_objects.active_review_progress import (
    ActiveReviewProgress,
)
from pr_auto_reviewer.domain.value_objects.capability_suspension import (
    CapabilitySuspension,
)
from pr_auto_reviewer.domain.value_objects.daemon_runtime_status import (
    DaemonRuntimeStatus,
)
from pr_auto_reviewer.domain.value_objects.daemon_state import DaemonState


class CapabilityQuery:
    def __init__(self, capabilities: tuple[ApiAccessCapability, ...]) -> None:
        self._capabilities = capabilities

    def statuses(self) -> tuple[ApiAccessCapability, ...]:
        return self._capabilities


class TestShowStatusService:
    def test_shows_suspended_api_capability_without_secret_value(self) -> None:
        state_port = MagicMock()
        state_port.read_status.return_value = None
        capability = ApiAccessCapability(
            platform="github",
            role="reviewer",
            source_name="GITHUB_TOKEN_acme_REVIEWER",
            scope="acme/widgets",
            suspension=CapabilitySuspension(
                suspended_until=time.time() + 3_600,
                resource="core",
                remaining=0,
                limit=5_000,
                reason="rate_limit_exhausted",
            ),
        )
        additional_capability = ApiAccessCapability(
            platform="forgejo",
            role="owner",
            source_name="FORGEJO_OWNER_TOKEN",
            scope="gbrennon/example",
        )
        service = ShowStatusService(
            runtime_state=state_port,
            process_checker=lambda pid: False,
            allowed_repositories=(),
            capability_query=CapabilityQuery((capability, additional_capability)),
        )

        output = service.show_status()

        assert "API Access Capabilities" in output
        assert "GITHUB_TOKEN_acme_REVIEWER" in output
        assert "\\n" not in output
        assert "API Access Capabilities" in output
        assert "  - forgejo:" in output
        assert "    - owner / FORGEJO_OWNER_TOKEN:" in output
        assert "available" not in output
        assert "      - gbrennon/example" in output
        assert "  - github:" in output
        assert "    - reviewer / GITHUB_TOKEN_acme_REVIEWER: suspended (1h 00m remaining)" in output
        assert "      - acme/widgets" in output
        assert "rate-limit-secret" not in output

    """Verifies human-readable status formatting across daemon lifecycle states."""

    def test_shows_idle_waiting_status(self) -> None:
        state_port = MagicMock()
        status = DaemonRuntimeStatus(
            pid=1234,
            daemon_mode=True,
            state=DaemonState.IDLE,
            updated_at="2026-11-09T18:00:00Z",
            poll_interval_seconds=600,
            allowed_repositories=("owner/repo-a", "owner/repo-b"),
            current_cycle=3,
            next_cycle_at="2026-11-09T18:10:00Z",
        )
        state_port.read_status.return_value = status
        service = ShowStatusService(
            runtime_state=state_port,
            process_checker=lambda pid: True,
            allowed_repositories=("owner/repo-a", "owner/repo-b"),
        )

        output = service.show_status()

        assert "Daemon: RUNNING (PID 1234)" in output
        assert "Status: IDLE / WAITING" in output
        assert "  - unscoped:\n    - owner:\n      - repo-a\n      - repo-b" in output
        assert "Next cycle" in output

    def test_groups_allowed_repositories_by_platform_and_organization(self) -> None:
        state_port = MagicMock()
        state_port.read_status.return_value = None
        service = ShowStatusService(
            runtime_state=state_port,
            process_checker=lambda pid: False,
            allowed_repositories=(
                "forgejo:gbrennon/ephact",
                "github:forging-blocks-org/forging-blocks",
                "forgejo:gbrennon/LocalNar",
            ),
        )

        output = service.show_status()

        assert "Allowed Repositories (3):\n  - forgejo:" in output
        assert "    - gbrennon:\n      - LocalNar\n      - ephact" in output
        assert "  - github:\n    - forging-blocks-org:\n      - forging-blocks" in output

    def test_shows_reviewing_status_with_phase_and_subagent(self) -> None:
        state_port = MagicMock()
        review = ActiveReviewProgress(
            repository="gbrennon/pr-auto-reviewer",
            pr_number=199,
            pr_title="Fix binary file decode error",
            head_sha="c9bec34",
            started_at="2026-11-09T18:05:00Z",
            phase_name="Bug Hunt — Diff",
            phase_index=1,
            total_phases=3,
            subagent_role="engineer",
            current_turn=3,
            max_turns=11,
            last_tool_call="read_file",
            last_tool_args="src/main.py",
        )
        status = DaemonRuntimeStatus(
            pid=1234,
            daemon_mode=True,
            state=DaemonState.REVIEWING,
            updated_at="2026-11-09T18:06:00Z",
            poll_interval_seconds=600,
            allowed_repositories=("gbrennon/pr-auto-reviewer",),
            current_cycle=1,
            current_review=review,
        )
        state_port.read_status.return_value = status
        service = ShowStatusService(
            runtime_state=state_port,
            process_checker=lambda pid: True,
            allowed_repositories=("gbrennon/pr-auto-reviewer",),
        )

        output = service.show_status()

        assert "Status: REVIEWING (Phase 1/3)" in output
        assert "gbrennon/pr-auto-reviewer #199" in output
        assert "Phase: Bug Hunt — Diff [engineer]" in output
        assert "Turn 3/11" in output
        assert "read_file(src/main.py)" in output

    def test_shows_stopped_when_pid_not_alive(self) -> None:
        state_port = MagicMock()
        status = DaemonRuntimeStatus(
            pid=999999,
            daemon_mode=True,
            state=DaemonState.IDLE,
            updated_at="2026-11-09T18:00:00Z",
            poll_interval_seconds=600,
            allowed_repositories=(),
        )
        state_port.read_status.return_value = status
        service = ShowStatusService(
            runtime_state=state_port,
            process_checker=lambda pid: False,
            allowed_repositories=(),
        )

        output = service.show_status()

        assert "Daemon: STOPPED" in output

    def test_shows_error_information_when_present(self) -> None:
        state_port = MagicMock()
        status = DaemonRuntimeStatus(
            pid=1234,
            daemon_mode=True,
            state=DaemonState.ERROR,
            updated_at="2026-11-09T18:00:00Z",
            poll_interval_seconds=600,
            allowed_repositories=(),
            last_error="LLM host unreachable",
            last_error_at="2026-11-09T18:00:00Z",
        )
        state_port.read_status.return_value = status
        service = ShowStatusService(
            runtime_state=state_port,
            process_checker=lambda pid: True,
            allowed_repositories=(),
        )

        output = service.show_status()

        assert "Last Error: LLM host unreachable" in output
