"""AdvisorCorrectionRenderer — composes the post-block restart prompt."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class AdvisorCorrectionRenderer(BaseMessageRenderer):
    """Compose the corrected restart prompt after an advisor block."""

    template_name = "orchestrator/advisor_correction.j2"
