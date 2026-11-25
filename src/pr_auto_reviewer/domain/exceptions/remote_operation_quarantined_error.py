from __future__ import annotations


class RemoteOperationQuarantinedError(RuntimeError):
    """Raised when a remote operation is temporarily quarantined."""

    def __init__(self, key: str, remaining_seconds: float) -> None:
        self.key = key
        self.remaining_seconds = remaining_seconds
        super().__init__(
            f"Remote operation {key} is quarantined for "
            f"{remaining_seconds:.1f} more seconds"
        )
