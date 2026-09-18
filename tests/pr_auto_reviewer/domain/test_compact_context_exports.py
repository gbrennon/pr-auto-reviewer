"""Tests for compact context domain exports."""

from pr_auto_reviewer.domain import (
    ContextCompactor,
    ContextWindow,
    Session,
    TokenCount,
    TokenUsage,
)


def test_compact_context_types_are_exported_from_domain_package() -> None:
    assert all((ContextCompactor, ContextWindow, Session, TokenCount, TokenUsage))
