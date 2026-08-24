"""AdvisorFeedbackMessageRenderer — injects a non-blocking advisor nudge."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class AdvisorFeedbackMessageRenderer(BaseMessageRenderer):
    """Inject a non-blocking advisor nudge back onto the task."""

    template_name = "review_phase/advisor_feedback.j2"
