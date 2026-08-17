"""Raised when a CommentId value is empty."""

from .domain_error import DomainError


class InvalidCommentIdError(DomainError):
    """Raised when a CommentId value is empty."""
