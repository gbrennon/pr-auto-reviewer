"""CommandBusPort — send a command/message/event to the infrastructure layer."""

from collections.abc import Callable
from typing import Any, Protocol

Handler = Callable[[Any], Any]


class CommandBusPort(Protocol):
    def register(self, command_type: type, handler: Handler) -> None:
        ...

    def dispatch(self, command: Any) -> Any:
        ...
