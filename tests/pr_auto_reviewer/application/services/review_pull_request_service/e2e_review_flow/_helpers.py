"""Shared helpers, fixtures, and imports for the split test modules."""

import json
import logging
import re
from unittest.mock import MagicMock

import pytest

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.services.review_item_factory import ReviewItemFactory
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.context.architecture_detector import (
    ArchitectureDetector,
)
from pr_auto_reviewer.presentation.cli.runner import CliRunner
from pr_auto_reviewer.presentation.polling_daemon import (
    PollingDaemon,
    PollingDaemonConfig,
)
from pr_auto_reviewer.presentation.ports import (
    OpenPullRequest,
    PrListerPort,
    RepoInfo,
    RepoListerPort,
)

__all__ = ['ArchitectureDetector', 'CliRunner', 'CommitSha', 'IssueCategory', 'ItemSeverity', 'MagicMock', 'MockPrLister', 'MockRepoLister', 'OpenPullRequest', 'PollingDaemon', 'PollingDaemonConfig', 'PrListerPort', 'PullRequestDiff', 'PullRequestId', 'RepoInfo', 'RepoListerPort', 'ReviewItem', 'ReviewItemFactory', 'json', 'logging', 'pytest', 're']


class MockRepoLister(RepoListerPort):
    def __init__(self, repos: list[RepoInfo]) -> None:
        self._repos = repos
        self.call_count = 0

    def list_repos(self) -> list[RepoInfo]:
        self.call_count += 1
        return self._repos


class MockPrLister(PrListerPort):
    def __init__(self, prs: list[OpenPullRequest]) -> None:
        self._prs = prs
        self.call_count = 0
        self.last_repo = None

    def list_open(self, repository: str) -> list[OpenPullRequest]:
        self.call_count += 1
        self.last_repo = repository
        return self._prs

    def get_pr(self, repository: str, pr_number: int) -> OpenPullRequest | None:
        for p in self._prs:
            if p.pr_id.number == pr_number:
                return p
        return None
