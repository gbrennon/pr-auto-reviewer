"""FeedbackContextRenderer — renders zero-findings re-run feedback context."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class FeedbackContextRenderer(BaseMessageRenderer):
    """Render the zero-findings feedback context for a re-run."""

    template_name = "orchestrator/feedback_context.j2"
