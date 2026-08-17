"""RegisterIssueCommand — input for registering a review item as a tracker issue."""

from dataclasses import dataclass

from ...value_objects.commit_sha import CommitSha
from ...value_objects.pull_request_id import PullRequestId


@dataclass(frozen=True)
class RegisterIssueCommand:
    """Command to register a single review item as a tracker issue.

    Triggered by a PR comment containing the word "issue" followed by the
    short 4-character review-item ID (e.g. ``issue a3f2``).
    """

    pr_id: PullRequestId
    head_sha: CommitSha
    issue_id: str
    command_text: str
