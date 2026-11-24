from dataclasses import dataclass


@dataclass(frozen=True)
class ShowStatusRequest:
    """Request the current daemon status."""
