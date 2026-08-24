"""InitialUserMessageRenderer — renders the opening review-phase user message."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class InitialUserMessageRenderer(BaseMessageRenderer):
    """Render the opening user message for a review-phase conversation."""

    template_name = "review_phase/initial_user.j2"
