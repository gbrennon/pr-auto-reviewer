from typing import Protocol

from pr_auto_reviewer.application.dtos.list_allowed_repositories_request import (
    ListAllowedRepositoriesRequest,
)
from pr_auto_reviewer.application.dtos.list_allowed_repositories_response import (
    ListAllowedRepositoriesResponse,
)


class ListAllowedRepositories(Protocol):
    """Lists normalized repositories permitted by the configured allowlist."""

    def execute(
        self, request: ListAllowedRepositoriesRequest
    ) -> ListAllowedRepositoriesResponse:
        """Return the repositories permitted by the current configuration."""
        ...
