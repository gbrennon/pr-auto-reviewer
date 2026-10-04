from typing import Protocol


class RepositoryAllowListEntriesPort(Protocol):
    """Provides the configured raw repository allowlist entries."""

    def get_entries(self) -> tuple[str, ...]:
        """Return repository entries from the active configuration."""
        ...
