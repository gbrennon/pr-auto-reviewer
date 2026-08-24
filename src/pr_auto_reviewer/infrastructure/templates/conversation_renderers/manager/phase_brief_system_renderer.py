"""ManagerBriefSystemRenderer — system prompt for manager briefings."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class ManagerBriefSystemRenderer(BaseMessageRenderer):
    """System prompt for the between-phases manager briefing."""

    template_name = "manager/phase_brief_system.j2"
    role = "system"
