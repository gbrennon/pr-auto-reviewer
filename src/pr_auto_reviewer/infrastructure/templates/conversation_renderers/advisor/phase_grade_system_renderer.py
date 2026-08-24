"""AdvisorPhaseGradeSystemRenderer — system prompt for finished-phase grading."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class AdvisorPhaseGradeSystemRenderer(BaseMessageRenderer):
    """System prompt for grading a finished phase."""

    template_name = "advisor/phase_grade_system.j2"
    role = "system"
