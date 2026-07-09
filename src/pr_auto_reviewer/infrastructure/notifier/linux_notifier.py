"""LinuxNotifier — desktop notifications via notify-send."""

import subprocess
from collections.abc import Callable
from typing import Any

from pr_auto_reviewer.application.ports.outbound.notifier_port import NotifierPort


class LinuxNotifier(NotifierPort):
    def __init__(
        self,
        run_command: Callable[..., Any] | None = None,
    ) -> None:
        self._run = run_command if run_command is not None else subprocess.run

    def notify_success(self, context: str, detail: str = "") -> None:
        self._run(
            ["notify-send", f"pr-auto-reviewer: {context}", detail],
            capture_output=True,
            timeout=5,
        )

    def notify_error(self, context: str, error: Exception) -> None:
        self._run(
            ["notify-send", "pr-auto-reviewer: ERROR", f"{context}: {error}"],
            capture_output=True,
            timeout=5,
        )
