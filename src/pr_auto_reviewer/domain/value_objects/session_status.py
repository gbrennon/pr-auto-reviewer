"""Session lifecycle status values."""

from enum import Enum


class SessionStatus(str, Enum):
    """Lifecycle states for a review session."""

    INITIALIZED = "initialized"
    ACTIVE = "active"
    COMPACTING = "compacting"
    COMPLETED = "completed"
    FAILED = "failed"

    @property
    def is_terminal(self) -> bool:
        """Whether the status cannot accept further mutations."""
        return self in (SessionStatus.COMPLETED, SessionStatus.FAILED)

    @property
    def can_accept_messages(self) -> bool:
        """Whether the status accepts appended conversation messages."""
        return self in (SessionStatus.INITIALIZED, SessionStatus.ACTIVE)
