from pr_auto_reviewer.presentation.ports import RepoInfo, RepoListerPort


class ScenarioRepoLister(RepoListerPort):
    """Lists the repository used by a review scenario."""

    def __init__(self, repository: str) -> None:
        self._repository = repository

    def list_repos(self) -> list[RepoInfo]:
        return [RepoInfo(self._repository)]
