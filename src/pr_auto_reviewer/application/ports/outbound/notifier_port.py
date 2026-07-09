"""NotifierPort — send system notifications to the user's desktop."""

from typing import Protocol


class NotifierPort(Protocol):
    def notify_success(self, context: str, detail: str = "") -> None:
        """Send a success notification."""
        ...

    def notify_error(self, context: str, error: Exception) -> None:
        """Send an error notification with context information."""
        ...
