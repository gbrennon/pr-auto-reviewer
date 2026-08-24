"""AdvisorBlockedError — the advisor blocked one conversation repeatedly."""

from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)


class AdvisorBlockedError(LlmUnavailableError):
    """Raised when the advisor blocks a conversation at its injected limit.

    This is a phase-local condition: the orchestrator restarts the
    offending phase instead of discarding the whole review sequence.
    """
