"""AdvisorBlockMessageRenderer — injects a blocking F-grade correction."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class AdvisorBlockMessageRenderer(BaseMessageRenderer):
    """Inject a blocking F-grade correction from the advisor."""

    template_name = "review_phase/advisor_block.j2"
