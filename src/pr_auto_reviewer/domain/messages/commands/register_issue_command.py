"""RegisterIssueCommand — input for registering a review item as a tracker issue."""

from dataclasses import dataclass

from ...value_objects.pull_request_id import PullRequestId


@dataclass(frozen=True)
class RegisterIssueCommand:
    """Command to register a single review item as a tracker issue.

    Triggered by a PR comment containing the word "issue" followed by the
    short review-item ID (e.g. ``issue a3f2``).
    """

    pr_id: PullRequestId
    issue_id: str
