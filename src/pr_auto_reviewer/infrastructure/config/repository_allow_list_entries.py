from pr_auto_reviewer.application.ports.outbound.repository_allow_list_entries_port import (
    RepositoryAllowListEntriesPort,
)


class ConfiguredRepositoryAllowListEntries(RepositoryAllowListEntriesPort):
    """Provides repository allowlist entries from application configuration."""

    def __init__(self, entries: tuple[str, ...]) -> None:
        self._entries = entries

    def get_entries(self) -> tuple[str, ...]:
        """Return the configured repository allowlist entries."""
        return self._entries
