"""RepositoryContextPort — fetch repo context for improved review quality."""

from typing import Protocol

from ....domain.value_objects.pull_request_id import PullRequestId
from ....domain.value_objects.repository_context import RepositoryContext


class RepositoryContextPort(Protocol):
    def fetch(self, pr_id: PullRequestId) -> RepositoryContext:
        ...
