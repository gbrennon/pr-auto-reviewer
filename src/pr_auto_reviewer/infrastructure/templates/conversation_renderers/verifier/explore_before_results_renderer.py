"""ExploreBeforeResultsRenderer — reprompt when verifier yields results with no tool calls."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class ExploreBeforeResultsRenderer(BaseMessageRenderer):
    """User message demanding exploration before results."""

    template_name = "verifier/explore_before_results.j2"
    role = "user"