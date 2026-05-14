"""OpenPullRequest DTO - represents an open pull request discovered during polling."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId


@dataclass(frozen=True)
class OpenPullRequest:
    """DTO for an open pull request discovered during polling."""

    pr_id: PullRequestId
    head_sha: CommitSha
    title: str
    description: str = ""
    is_draft: bool = False