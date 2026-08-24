"""AdvisorTurnGradeUserRenderer — user message for live turn grading."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class AdvisorTurnGradeUserRenderer(BaseMessageRenderer):
    """User message carrying the peer turn being graded."""

    template_name = "advisor/turn_grade_user.j2"
