"""EmptyResponseMessageRenderer — reprompts peers that return empty output."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class EmptyResponseMessageRenderer(BaseMessageRenderer):
    """Prompt a peer that returned an empty response to continue."""

    template_name = "review_phase/empty_response.j2"
