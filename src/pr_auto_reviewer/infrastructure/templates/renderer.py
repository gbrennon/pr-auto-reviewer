"""BaseMessageRenderer — shared renderer for all conversation message components.

Every conversation message in the review pipeline is a template component:
a ``.j2`` file holds the prose (with any JSON schema spelled exactly once),
and exactly one renderer class backs that template.  This base class
provides the shared Jinja2 machinery so every component renders through
the same code path; subclasses only declare which template they render
and what role the message takes.

Templates live under ``templates/conversation/``.  A component may
``{% include %}`` shared schema fragments so the JSON instructions a
peer model receives are identical across phases instead of being
re-spelled with drifting escapes in each call site.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import jinja2

from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)

_TEMPLATES_DIR = Path(__file__).resolve().parent / "conversation"


class BaseMessageRenderer:
    """Render one conversation-message template into a typed message.

    Subclasses set ``template_name`` and ``role``; callers invoke
    ``render(**context)`` to get a :class:`ConversationMessage`.  A
    custom ``template_dir`` may be injected for tests, defaulting to the
    canonical ``templates/conversation/`` directory.
    """

    template_name: str = ""
    role: str = "user"

    def __init__(self, template_dir: Path | None = None) -> None:
        self._env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_dir or _TEMPLATES_DIR)),
            keep_trailing_newline=True,
            undefined=jinja2.StrictUndefined,
        )

    def render_content(self, **context: Any) -> str:
        """Render the template body to a plain string."""
        return self._env.get_template(self.template_name).render(**context)

    def render(self, **context: Any) -> ConversationMessage:
        """Render this component into a typed conversation message."""
        return ConversationMessage(
            role=self.role, content=self.render_content(**context)
        )