"""Shared helpers, fixtures, and imports for the split test modules."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests as req

from pr_auto_reviewer.application.services.review_pull_request_service import (
    ReviewPullRequestService,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.messages.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.ollama.ollama_llm_adapter import (
    OllamaLlmAdapter,
)
from tests.fakes import (
    FakeChangesetFetcher,
    FakeLlmReview,
    FakePullRequestRepository,
    FakeReviewContextFactory,
    FakeReviewPublisher,
)

FIXTURES = next(p for p in Path(__file__).resolve().parents if p.name == "tests") / "fixtures"


def _load_fixture(relative: str) -> str:
    return (FIXTURES / relative).read_text()


__all__ = ['FIXTURES', 'CodeReview', 'CommitSha', 'ComposedPrompt', 'FakeChangesetFetcher', 'FakeLlmReview', 'FakePullRequestRepository', 'FakeReviewContextFactory', 'FakeReviewPublisher', 'IssueCategory', 'ItemSeverity', 'LlmUnavailableError', 'MagicMock', 'OllamaLlmAdapter', 'Path', 'PullRequestDiff', 'PullRequestId', 'ReviewItem', 'ReviewPullRequestCommand', 'ReviewPullRequestService', 'ReviewVerdict', '_load_fixture', 'annotations', 'json', 'pytest', 'req']
