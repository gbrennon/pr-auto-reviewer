"""Fake CliRunner for tests."""

from __future__ import annotations

import argparse
import logging
import sys
from unittest.mock import MagicMock

from pr_auto_reviewer.application.ports.inbound.process_issue_commands_use_case import (
    ProcessIssueCommandsUseCase,
)
from pr_auto_reviewer.application.ports.inbound.review_pull_request_use_case import (
    ReviewPullRequestUseCase,
)
from pr_auto_reviewer.application.ports.outbound.notifier_port import NotifierPort
from pr_auto_reviewer.application.ports.outbound.pull_request_repository import (
    PullRequestRepository,
)
from pr_auto_reviewer.application.ports.outbound.review_reader_port import (
    ReviewReaderPort,
)
from pr_auto_reviewer.application.ports.outbound.token_verifier_port import (
    TokenVerifierPort,
)
from pr_auto_reviewer.domain.exceptions.domain_error import DomainError
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError
from pr_auto_reviewer.domain.exceptions.pull_request_not_found_error import (
    PullRequestNotFoundError,
)
from pr_auto_reviewer.domain.exceptions.review_publish_error import ReviewPublishError
from pr_auto_reviewer.domain.messages.commands.process_issue_commands_command import (
    ProcessIssueCommandsCommand,
)
from pr_auto_reviewer.domain.messages.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)
from pr_auto_reviewer.domain.services.review_item_parser import ReviewItemParser
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.client.http_request_counter import (
    HttpRequestCounter,
)
from pr_auto_reviewer.presentation.ports import PrListerPort


class FakeCliRunner:
    """Fake CliRunner that tracks calls without running actual CLI."""

    def __init__(self) -> None:
        self._argv: list[str] | None = None
        self.run_calls: list[list[str]] = []
        self._review_result: int = 0

    def __init_subclass__(**kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

    def run(self, argv: list[str] | None = None) -> int:
        """Track run call without executing CLI."""
        self._argv = argv
        self.run_calls.append(argv if argv else sys.argv)
        return self._review_result

    def _run_review(self, argv: list[str]) -> int:
        """Track _run_review call."""
        self.run_calls.append(argv)
        return 0

    def _run_process_commands(self, argv: list[str]) -> int:
        """Track _run_process_commands call."""
        self.run_calls.append(argv)
        return 0

    def _run_list_items(self, argv: list[str]) -> int:
        """Track _run_list_items call."""
        self.run_calls.append(argv)
        return 0

    def _run_clean(self) -> int:
        """Track _run_clean call."""
        self.run_calls.append([])
        return 0


class FakeCliRunnerWithResult:
    """Fake CliRunner with configurable result."""

    def __init__(self, review_result: int = 0) -> None:
        self._review_result = review_result
        self.run_calls: list[list[str]] = []

    def run(self, argv: list[str] | None = None) -> int:
        """Track run call."""
        self.run_calls.append(argv if argv else sys.argv)
        return self._review_result

    def _run_review(self, argv: list[str]) -> int:
        """Track _run_review call."""
        self.run_calls.append(argv)
        return 0

    def _run_process_commands(self, argv: list[str]) -> int:
        """Track _run_process_commands call."""
        self.run_calls.append(argv)
        return 0

    def _run_list_items(self, argv: list[str]) -> int:
        """Track _run_list_items call."""
        self.run_calls.append(argv)
        return 0

    def _run_clean(self) -> int:
        """Track _run_clean call."""
        self.run_calls.append([])
        return 0