"""DaemonState — lifecycle states for the polling review daemon."""

from __future__ import annotations

from enum import Enum


class DaemonState(str, Enum):
    """Lifecycle states of the automated reviewer daemon."""

    STOPPED = "stopped"
    IDLE = "idle"
    REVIEWING = "reviewing"
    ERROR = "error"
