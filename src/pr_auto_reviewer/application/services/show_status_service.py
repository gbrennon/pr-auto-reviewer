"""ShowStatusService — compiles real-time daemon state into human-readable output."""

from __future__ import annotations

from dataclasses import replace

from pr_auto_reviewer.application.dtos.daemon_status_snapshot import (
    DaemonStatusSnapshot,
)
from pr_auto_reviewer.application.dtos.show_status_request import ShowStatusRequest
from pr_auto_reviewer.application.dtos.show_status_response import ShowStatusResponse
from pr_auto_reviewer.application.ports.inbound.show_status_port import ShowStatusPort
from pr_auto_reviewer.application.ports.outbound.api_access_capability_query_port import (
    ApiAccessCapabilityQueryPort,
)
from pr_auto_reviewer.application.ports.outbound.daemon_runtime_state_port import (
    DaemonRuntimeStatePort,
)
from pr_auto_reviewer.application.ports.outbound.process_liveness_port import (
    ProcessLivenessPort,
)


class ShowStatusService(ShowStatusPort):
    """Retrieve daemon status through outbound ports."""

    def __init__(
        self,
        runtime_state: DaemonRuntimeStatePort,
        process_liveness: ProcessLivenessPort,
        allowed_repositories: tuple[str, ...],
        poll_interval_seconds: int | None = None,
        capability_query: ApiAccessCapabilityQueryPort | None = None,
    ) -> None:
        self._runtime_state = runtime_state
        self._process_liveness = process_liveness
        self._allowed_repositories = allowed_repositories
        self._poll_interval_seconds = poll_interval_seconds
        self._capability_query = capability_query

    def execute(self, request: ShowStatusRequest) -> ShowStatusResponse:
        """Return the current daemon status through the injected ports."""
        _ = request
        stored_status = self._runtime_state.read_status()
        status = (
            replace(
                stored_status,
                poll_interval_seconds=self._poll_interval_seconds,
            )
            if stored_status is not None and self._poll_interval_seconds is not None
            else stored_status
        )
        daemon_alive = (
            status is not None and self._process_liveness.is_alive(status.pid)
        )
        capabilities = (
            self._capability_query.statuses()
            if self._capability_query is not None
            else ()
        )
        return ShowStatusResponse(
            snapshot=DaemonStatusSnapshot(
                runtime_status=status,
                daemon_alive=daemon_alive,
                allowed_repositories=self._allowed_repositories,
                capabilities=tuple(capabilities),
            )
        )
