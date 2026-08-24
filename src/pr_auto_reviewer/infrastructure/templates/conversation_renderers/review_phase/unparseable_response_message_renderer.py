"""UnparseableResponseMessageRenderer — reprompts peers that emit non-JSON."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class UnparseableResponseMessageRenderer(BaseMessageRenderer):
    """Prompt a peer that returned non-JSON to respond with valid JSON."""

    template_name = "review_phase/unparseable_response.j2"
