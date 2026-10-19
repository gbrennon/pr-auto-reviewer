from pr_auto_reviewer.presentation.ports import OpenPullRequest, PrListerPort


class ScenarioPrLister(PrListerPort):
    """Restricts pull-request discovery to the scenario's pull request."""

    def __init__(self, delegate: PrListerPort, pr_number: int) -> None:
        self._delegate = delegate
        self._pr_number = pr_number

    def list_recent(
        self, repository: str, since: str,
    ) -> list[OpenPullRequest]:
        return []

    def list_open(self, repository: str) -> list[OpenPullRequest]:
        pull_request = self._delegate.get_pr(repository, self._pr_number)
        return [pull_request] if pull_request is not None else []

    def get_pr(
        self, repository: str, pr_number: int,
    ) -> OpenPullRequest | None:
        return self._delegate.get_pr(repository, pr_number)
