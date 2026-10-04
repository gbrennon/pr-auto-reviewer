from pr_auto_reviewer.application.dtos.list_allowed_repositories_request import (
    ListAllowedRepositoriesRequest,
)
from pr_auto_reviewer.application.ports.outbound.repository_allow_list_entries_port import (
    RepositoryAllowListEntriesPort,
)
from pr_auto_reviewer.application.services.list_allowed_repositories_service import (
    ListAllowedRepositoriesService,
)


class RepositoryAllowListEntriesFake(RepositoryAllowListEntriesPort):
    def __init__(self, entries: tuple[str, ...]) -> None:
        self._entries = entries

    def get_entries(self) -> tuple[str, ...]:
        return self._entries


class TestListAllowedRepositoriesService:
    def test_lists_normalized_allowed_repositories(self) -> None:
        service = ListAllowedRepositoriesService(
            RepositoryAllowListEntriesFake(
                (" codeberg:Owner/Repo ", "github:team/api")
            )
        )

        response = service.execute(ListAllowedRepositoriesRequest())

        assert response.allowed_repositories == (
            "forgejo:owner/repo",
            "github:team/api",
        )
        assert response.allows_every_repository is False

    def test_reports_that_empty_configuration_allows_every_repository(self) -> None:
        service = ListAllowedRepositoriesService(
            RepositoryAllowListEntriesFake(())
        )

        response = service.execute(ListAllowedRepositoriesRequest())

        assert response.allowed_repositories == ()
        assert response.allows_every_repository is True
