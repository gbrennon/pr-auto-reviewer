"""VerifyInitialUserRenderer — opening message for verification conversations."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class VerifyInitialUserRenderer(BaseMessageRenderer):
    """Opening user message for a findings-verification conversation."""

    template_name = "verifier/initial_user.j2"
