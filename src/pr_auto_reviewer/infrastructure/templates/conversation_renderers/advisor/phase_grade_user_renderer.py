"""AdvisorPhaseGradeUserRenderer — user message for finished-phase grading."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class AdvisorPhaseGradeUserRenderer(BaseMessageRenderer):
    """User message carrying the finished phase outcome to grade."""

    template_name = "advisor/phase_grade_user.j2"
