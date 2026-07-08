"""PromptRendererPort — port for rendering fragment templates with variables."""

from __future__ import annotations

from typing import Protocol

class PromptRendererPort(Protocol):
    """Port for rendering fragment templates with variable substitution.

    Implementations may use simple string replacement, Jinja2, or any
    other templating engine.  The contract only requires a ``render``
    method that accepts a template string and a variable dictionary.
    """

    def render(self, template: str, variables: dict[str, str]) -> str:
        """Render *template* with *variables* and return the resulting string.

        Args:
            template: A template string (e.g. Markdown with ``{{ placeholders }}``).
            variables: Key/value pairs to substitute into the template.

        Returns:
            The rendered content.

        Raises:
            ValueError: If the template cannot be rendered (malformed syntax,
                missing required variables, etc.).
        """
        ...
