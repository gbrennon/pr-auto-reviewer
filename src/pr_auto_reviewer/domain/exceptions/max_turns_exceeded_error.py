"""MaxTurnsExceededError — a conversation exhausted its injected turn limit."""

from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)


class MaxTurnsExceededError(LlmUnavailableError):
    """Raised when a conversation reaches its maximum turn count
    without producing a verdict.
    """
