"""AdvisorTurnGradeSystemRenderer — system prompt for live turn grading."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class AdvisorTurnGradeSystemRenderer(BaseMessageRenderer):
    """System prompt for grading a single live peer turn."""

    template_name = "advisor/turn_grade_system.j2"
    role = "system"
