"""RepeatedToolCallMessageRenderer — refuses duplicate tool calls."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class RepeatedToolCallMessageRenderer(BaseMessageRenderer):
    """Refuse a repeated tool call and direct the peer onward."""

    template_name = "review_phase/repeated_tool_call.j2"
