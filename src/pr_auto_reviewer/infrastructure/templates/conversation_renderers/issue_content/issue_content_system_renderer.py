"""IssueContentSystemRenderer — system prompt for preparing tracker issue content."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class IssueContentSystemRenderer(BaseMessageRenderer):
    """System prompt for converting a review finding to a tracker issue."""

    template_name = "issue_content/system.j2"
    role = "system"
