"""ForceVerdictMessageRenderer — nudges an over-exploring peer to conclude."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class ForceVerdictMessageRenderer(BaseMessageRenderer):
    """Nudge a peer that has explored enough to conclude with a verdict."""

    template_name = "review_phase/force_verdict.j2"
