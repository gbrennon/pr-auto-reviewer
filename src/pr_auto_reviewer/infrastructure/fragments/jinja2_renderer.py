"""Jinja2Renderer — renders fragment templates with the Jinja2 engine."""

from __future__ import annotations

import logging
from typing import Any

from jinja2 import BaseLoader, Environment, StrictUndefined, TemplateError

logger = logging.getLogger(__name__)

class Jinja2Renderer:
    """Renders prompt templates using the Jinja2 template engine.

    Supports the full Jinja2 feature set:

    - Variable substitution: ``{{ variable }}``
    - Conditionals: ``{% if condition %}...{% endif %}``
    - Loops: ``{% for item in items %}...{% endfor %}``
    - Filters: ``{{ variable|upper }}``, ``{{ var|default('N/A') }}``
    """

    def __init__(self) -> None:
        """Initialise the renderer with a basic Jinja2 environment.

        Templates are loaded from strings (not the filesystem), so we
        use :class:`BaseLoader`.  Auto-escaping is disabled because we
        are rendering Markdown prompts, not HTML.
        """
        self._env = Environment(
            loader=BaseLoader(),
            autoescape=False,
            undefined=StrictUndefined,
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def render(self, template: str, variables: dict[str, Any]) -> str:
        """Render *template* with *variables*.

        Args:
            template: A Jinja2 template string.
            variables: Key/value pairs for substitution.

        Returns:
            The rendered string.

        Raises:
            ValueError: If the template is malformed or references an
                undefined variable without a ``default()`` filter.
        """
        try:
            jinja_template = self._env.from_string(template)
            result = jinja_template.render(**variables)
            return result
        except TemplateError as exc:
            logger.exception(
                "Template rendering failed for template string: %s", template,
            )
            raise ValueError(f"Template rendering failed: {exc}") from exc
