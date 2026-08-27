"""SuggestionsPraiseMessageRenderer — prompts peer for architectural suggestions and praise."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class SuggestionsPraiseMessageRenderer(BaseMessageRenderer):
    """Prompt peer specifically for architectural suggestions and praise."""

    template_name = "review_phase/suggestions_praise.j2"
