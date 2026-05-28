"""InMemoryCommandBus — infrastructure adapter that dispatches commands.

Implements CommandBusPort. A simple in-memory dispatcher that routes
command objects to the registered handler callable.

This is the simplest possible bus — commands are dispatched synchronously
in the same process. Can be swapped for a message-queue-based bus without
touching application or domain code.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from ...application.ports.outbound.command_bus_port import CommandBusPort

logger = logging.getLogger(__name__)


Handler = Callable[[Any], None]


class InMemoryCommandBus(CommandBusPort):
    """Synchronous in-memory command dispatcher.

    Handlers are registered at construction time by the composition root.
    Unknown command types are silently ignored (fire-and-forget semantics).
    """

    def __init__(
        self,
        handlers: dict[type, Handler] | None = None,
    ) -> None:
        self._handlers: dict[type, Handler] = dict(handlers) if handlers else {}

    def register(self, command_type: type, handler: Handler) -> None:
        """Register a handler for a command type."""
        self._handlers[command_type] = handler

    def dispatch(self, command: Any) -> None:
        cmd_type = type(command).__name__
        handler = self._handlers.get(type(command))
        if handler is not None:
            handler_name = getattr(handler, "__name__", type(handler).__name__)
            logger.debug("Dispatching %s to %s", cmd_type, handler_name)
            handler(command)
        else:
            logger.debug("No handler registered for %s (fire-and-forget)", cmd_type)
