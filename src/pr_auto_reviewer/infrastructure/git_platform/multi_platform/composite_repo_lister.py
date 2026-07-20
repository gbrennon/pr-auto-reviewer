from pr_auto_reviewer.presentation.ports.repo_info import RepoInfo
from pr_auto_reviewer.presentation.ports.repo_lister_port import RepoListerPort


class CompositeRepoLister(RepoListerPort):
    def __init__(self, listers: dict[str, RepoListerPort]) -> None:
        self._listers = listers

    def list_repos(self) -> list[RepoInfo]:
        result: list[RepoInfo] = []
        for platform, lister in self._listers.items():
            for info in lister.list_repos():
                result.append(RepoInfo(
                    full_name=f"{platform}:{info.full_name}",
                    pushed_at=info.pushed_at,
                ))
        return result
