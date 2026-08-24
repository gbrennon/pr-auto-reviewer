"""ExploreBeforeVerdictMessageRenderer — demands exploration before verdicts."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class ExploreBeforeVerdictMessageRenderer(BaseMessageRenderer):
    """Demand exploration before accepting a zero-tool-call verdict."""

    template_name = "review_phase/explore_before_verdict.j2"
