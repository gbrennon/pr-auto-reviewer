"""Shared helpers, fixtures, and imports for the split test modules."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pr_auto_reviewer.application.services import ReviewPullRequestService
from pr_auto_reviewer.domain import (
    CodeReview,
    CommitSha,
    EmptyDiffError,
    IssueCategory,
    ItemSeverity,
    PullRequest,
    PullRequestDiff,
    PullRequestId,
    ReviewVerdict,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.messages.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures" / "diffs"


def _pr_id(repo="owner/repo", num=42):
    return PullRequestId(repository=repo, number=num)


def _sha(v="abc123"):
    return CommitSha(value=v)


def _cmd(pr_id=None, sha=None):
    return ReviewPullRequestCommand(
        pr_id=pr_id or _pr_id(),
        head_sha=sha or _sha(),
        title="Add feature X",
    )


def _diff_fixture(pr_id, sha):
    return PullRequestDiff(
        pr_id=pr_id,
        head_sha=sha,
        diff_content=(FIXTURES / "sample-service.diff").read_text(),
        file_contents={"src/main.py": "def hello(): pass\n"},
    )


def _review(verdict=ReviewVerdict.APPROVED, items=None):
    return CodeReview(
        verdict=verdict,
        items=items or [],
        summary="Looks good",
        model_used="test",
        reason="test reason",
    )


def _pr(pr_id, sha):
    return PullRequest(id=pr_id, title="Add feature X", head_sha=sha)


__all__ = ['FIXTURES', 'CodeReview', 'CommitSha', 'ComposedPrompt', 'EmptyDiffError', 'IssueCategory', 'ItemSeverity', 'MagicMock', 'Path', 'PullRequest', 'PullRequestDiff', 'PullRequestId', 'ReviewItem', 'ReviewPullRequestCommand', 'ReviewPullRequestService', 'ReviewVerdict', '_cmd', '_diff_fixture', '_pr', '_pr_id', '_review', '_sha', 'annotations', 'logging', 'pytest']
