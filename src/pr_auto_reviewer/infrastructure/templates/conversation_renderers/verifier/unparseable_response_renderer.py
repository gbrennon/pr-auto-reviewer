"""VerifyUnparseableResponseRenderer — reprompts a non-JSON verifier reply."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class VerifyUnparseableResponseRenderer(BaseMessageRenderer):
    """Prompt a verifier that returned non-JSON."""

    template_name = "verifier/unparseable_response.j2"
