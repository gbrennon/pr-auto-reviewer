"""Fake CliRunner for tests."""

from __future__ import annotations

import sys
from typing import Any


class FakeCliRunner:
    """Fake CliRunner that tracks calls without running actual CLI."""

    def __init__(self) -> None:
        self._argv: list[str] | None = None
        self.run_calls: list[list[str]] = []
        self._review_result: int = 0

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super(FakeCliRunner, cls).__init_subclass__(**kwargs)

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