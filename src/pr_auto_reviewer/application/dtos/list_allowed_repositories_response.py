from dataclasses import dataclass


@dataclass(frozen=True)
class ListAllowedRepositoriesResponse:
    """Result containing normalized allowed repositories and access scope."""

    allowed_repositories: tuple[str, ...]
    allows_every_repository: bool
