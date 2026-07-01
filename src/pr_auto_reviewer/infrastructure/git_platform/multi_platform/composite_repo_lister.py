from pr_auto_reviewer.presentation.ports.repo_lister_port import RepoListerPort


class CompositeRepoLister(RepoListerPort):
    def __init__(self, listers: dict[str, RepoListerPort]) -> None:
        self._listers = listers

    def list_repos(self) -> list[str]:
        result: list[str] = []
        for platform, lister in self._listers.items():
            for repo in lister.list_repos():
                result.append(f"{platform}:{repo}")
        return result
