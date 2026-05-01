"""Domain-level exceptions for the pr-auto-reviewer bounded context."""


class DomainError(Exception):
    """Base exception for all domain errors."""


class InvalidCommitShaError(DomainError):
    """Raised when a CommitSha value is empty or invalid."""


class InvalidPullRequestIdError(DomainError):
    """Raised when a PullRequestId has invalid repository or number."""


class InvalidCommentIdError(DomainError):
    """Raised when a CommentId value is empty."""


class InvalidIssueBodyError(DomainError):
    """Raised when an issue body or title is empty."""
