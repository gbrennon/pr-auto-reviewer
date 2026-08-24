"""VerifyEmptyResponseRenderer — reprompts an empty verifier response."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.templates.renderer import (
    BaseMessageRenderer,
)


class VerifyEmptyResponseRenderer(BaseMessageRenderer):
    """Prompt a verifier that returned an empty response."""

    template_name = "verifier/empty_response.j2"
