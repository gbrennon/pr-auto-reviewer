"""ManagerBriefUserRenderer — user message for manager briefings."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class ManagerBriefUserRenderer(BaseMessageRenderer):
    """User message carrying the upcoming phase and prior findings."""

    template_name = "manager/phase_brief_user.j2"
