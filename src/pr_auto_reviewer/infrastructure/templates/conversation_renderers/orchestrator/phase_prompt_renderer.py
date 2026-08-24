"""PhasePromptRenderer — assembles the layered system prompt for a phase."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class PhasePromptRenderer(BaseMessageRenderer):
    """Assemble the layered system prompt for one review phase."""

    template_name = "orchestrator/phase_prompt.j2"
