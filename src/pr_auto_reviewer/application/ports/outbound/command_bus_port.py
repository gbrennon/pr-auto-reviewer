"""CommandBusPort — send a command/message/event to the infrastructure layer."""

from typing import Any, Protocol

class CommandBusPort(Protocol):
    def dispatch(self, command: Any) -> None:
        ...
