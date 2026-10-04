from pr_auto_reviewer.application.dtos.list_allowed_repositories_request import (
    ListAllowedRepositoriesRequest,
)
from pr_auto_reviewer.application.dtos.list_allowed_repositories_response import (
    ListAllowedRepositoriesResponse,
)
from pr_auto_reviewer.application.ports.inbound.list_allowed_repositories import (
    ListAllowedRepositories,
)
from pr_auto_reviewer.application.ports.outbound.repository_allow_list_entries_port import (
    RepositoryAllowListEntriesPort,
)
from pr_auto_reviewer.domain.services.repository_allow_list import RepositoryAllowList


class ListAllowedRepositoriesService(ListAllowedRepositories):
    """Returns the normalized repositories permitted by configuration."""

    def __init__(self, entries_port: RepositoryAllowListEntriesPort) -> None:
        self._entries_port = entries_port

    def execute(
        self, request: ListAllowedRepositoriesRequest
    ) -> ListAllowedRepositoriesResponse:
        """Build a primitive response from the configured repository entries."""
        _ = request
        allow_list = RepositoryAllowList.from_entries(
            self._entries_port.get_entries()
        )
        return ListAllowedRepositoriesResponse(
            allowed_repositories=tuple(sorted(allow_list.allowed_repositories)),
            allows_every_repository=allow_list.allows_every_repository,
        )
