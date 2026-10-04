from dataclasses import dataclass


@dataclass(frozen=True)
class ListAllowedRepositoriesRequest:
    """Request to retrieve the configured allowed repositories."""
