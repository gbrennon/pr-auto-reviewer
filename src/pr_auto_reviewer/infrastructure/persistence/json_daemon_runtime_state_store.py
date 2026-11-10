"""JsonDaemonRuntimeStateStore — atomic JSON file persistence for daemon telemetry."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

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

logger = logging.getLogger(__name__)


class JsonDaemonRuntimeStateStore(DaemonRuntimeStatePort):
    """Persists daemon runtime telemetry into an atomically-written JSON file."""

    def __init__(self, state_path: Path) -> None:
        self._state_path = state_path

    def record_status(self, status: DaemonRuntimeStatus) -> None:
        """Atomically serialize and write status to disk."""
        data = self._serialize_status(status)
        parent = self._state_path.parent
        parent.mkdir(parents=True, exist_ok=True)
        tmp_path = self._state_path.with_suffix(".tmp")
        try:
            tmp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            os.replace(tmp_path, self._state_path)
        except OSError:
            logger.warning(
                "Could not write daemon status to %s",
                self._state_path,
                exc_info=True,
            )

    def read_status(self) -> DaemonRuntimeStatus | None:
        """Read and deserialize the daemon runtime status file."""
        if not self._state_path.is_file():
            return None
        try:
            content = self._state_path.read_text(encoding="utf-8")
            data = json.loads(content)
            return self._deserialize_status(data)
        except (OSError, json.JSONDecodeError, KeyError, ValueError):
            logger.warning(
                "Could not parse daemon status file %s",
                self._state_path,
                exc_info=True,
            )
            return None

    def clear(self) -> None:
        """Remove status file on clean shutdown."""
        try:
            if self._state_path.exists():
                self._state_path.unlink()
        except OSError:
            logger.warning(
                "Could not delete status file %s",
                self._state_path,
                exc_info=True,
            )

    @classmethod
    def _serialize_status(cls, status: DaemonRuntimeStatus) -> dict[str, Any]:
        data: dict[str, Any] = {
            "pid": status.pid,
            "daemon_mode": status.daemon_mode,
            "state": status.state.value,
            "updated_at": status.updated_at,
            "poll_interval_seconds": status.poll_interval_seconds,
            "allowed_repositories": list(status.allowed_repositories),
            "current_cycle": status.current_cycle,
            "next_cycle_at": status.next_cycle_at,
            "last_error": status.last_error,
            "last_error_at": status.last_error_at,
            "current_review": None,
        }
        review = status.current_review
        if review is not None:
            data["current_review"] = {
                "repository": review.repository,
                "pr_number": review.pr_number,
                "pr_title": review.pr_title,
                "head_sha": review.head_sha,
                "started_at": review.started_at,
                "phase_name": review.phase_name,
                "phase_index": review.phase_index,
                "total_phases": review.total_phases,
                "subagent_role": review.subagent_role,
                "current_turn": review.current_turn,
                "max_turns": review.max_turns,
                "last_tool_call": review.last_tool_call,
                "last_tool_args": review.last_tool_args,
            }
        return data

    @classmethod
    def _deserialize_status(cls, data: dict[str, Any]) -> DaemonRuntimeStatus:
        review_data = data.get("current_review")
        review = None
        if isinstance(review_data, dict):
            review = ActiveReviewProgress(
                repository=str(review_data.get("repository", "")),
                pr_number=int(review_data.get("pr_number", 0)),
                pr_title=str(review_data.get("pr_title", "")),
                head_sha=str(review_data.get("head_sha", "")),
                started_at=str(review_data.get("started_at", "")),
                phase_name=str(review_data.get("phase_name", "")),
                phase_index=int(review_data.get("phase_index", 0)),
                total_phases=int(review_data.get("total_phases", 0)),
                subagent_role=str(review_data.get("subagent_role", "")),
                current_turn=int(review_data.get("current_turn", 0)),
                max_turns=int(review_data.get("max_turns", 0)),
                last_tool_call=str(review_data.get("last_tool_call", "")),
                last_tool_args=str(review_data.get("last_tool_args", "")),
            )
        allowed = tuple(data.get("allowed_repositories", []))
        return DaemonRuntimeStatus(
            pid=int(data["pid"]),
            daemon_mode=bool(data.get("daemon_mode", True)),
            state=DaemonState(data["state"]),
            updated_at=str(data["updated_at"]),
            poll_interval_seconds=int(data["poll_interval_seconds"]),
            allowed_repositories=allowed,
            current_cycle=int(data.get("current_cycle", 0)),
            next_cycle_at=data.get("next_cycle_at"),
            current_review=review,
            last_error=data.get("last_error"),
            last_error_at=data.get("last_error_at"),
        )
