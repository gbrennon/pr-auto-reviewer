from typing import Protocol


class ProcessLivenessPort(Protocol):
    """Check whether an operating-system process is currently alive."""

    def is_alive(self, pid: int) -> bool:
        """Return whether the process identified by ``pid`` is alive."""
        ...
