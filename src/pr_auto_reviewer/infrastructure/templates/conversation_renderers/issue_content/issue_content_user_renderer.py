"""IssueContentUserRenderer — user message for preparing tracker issue content."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class IssueContentUserRenderer(BaseMessageRenderer):
    """User message carrying finding details for issue creation."""

    template_name = "issue_content/user.j2"
