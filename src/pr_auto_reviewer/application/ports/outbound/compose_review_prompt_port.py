"""ComposeReviewPromptPort — outbound port for composing a review prompt from fragments."""

from typing import Protocol

from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.fragments.entities.review_context import ReviewContext

class ComposeReviewPromptPort(Protocol):
    """Outbound port for composing a complete LLM review prompt from fragments.

    Implemented by infrastructure adapters.  Satisfied by any object
    that implements ``execute`` with a ``ReviewContext``.
    """

    def execute(self, context: ReviewContext) -> ComposedPrompt:
        ...

