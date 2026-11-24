import os


class SystemProcessLiveness:
    """Check process liveness using the host operating system."""

    def is_alive(self, pid: int) -> bool:
        """Return whether the process identified by ``pid`` is alive."""
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
        except (OSError, ProcessLookupError):
            return False
        return True
