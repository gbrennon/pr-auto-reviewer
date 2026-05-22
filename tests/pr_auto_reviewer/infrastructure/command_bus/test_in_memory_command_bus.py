"""Tests for InMemoryCommandBus."""

import pytest

from pr_auto_reviewer.infrastructure.command_bus.in_memory_command_bus import InMemoryCommandBus


class _RecordingHandler:
    """Stub handler that records received commands."""

    def __init__(self) -> None:
        self.commands: list = []
        self.call_count = 0

    def __call__(self, command) -> None:
        self.commands.append(command)
        self.call_count += 1

    def assert_called_once(self) -> None:
        assert self.call_count == 1, f"Expected 1 call, got {self.call_count}"

    def assert_called_once_with(self, command) -> None:
        assert self.call_count == 1, f"Expected 1 call, got {self.call_count}"
        assert self.commands[0] is command, f"Expected {command}, got {self.commands[0]}"


class TestInMemoryCommandBus:
    """Tests for InMemoryCommandBus."""

    @pytest.fixture
    def bus(self) -> InMemoryCommandBus:
        return InMemoryCommandBus()

    @pytest.fixture
    def bus_with_handlers(self) -> InMemoryCommandBus:
        handler1 = _RecordingHandler()
        handler2 = _RecordingHandler()
        return InMemoryCommandBus(handlers={
            SomeCommand: handler1,
            OtherCommand: handler2,
        })

    def test_init_empty_handlers(self, bus: InMemoryCommandBus) -> None:
        """Initializes with empty handlers dict."""
        assert bus._handlers == {}

    def test_init_with_handlers(self, bus_with_handlers: InMemoryCommandBus) -> None:
        """Initializes with provided handlers."""
        assert len(bus_with_handlers._handlers) == 2
        assert SomeCommand in bus_with_handlers._handlers
        assert OtherCommand in bus_with_handlers._handlers

    def test_register_adds_handler(self, bus: InMemoryCommandBus) -> None:
        """Register adds a handler to the handlers dict."""
        handler = _RecordingHandler()
        bus.register(SomeCommand, handler)
        assert bus._handlers[SomeCommand] is handler

    def test_register_overwrites_existing_handler(self, bus: InMemoryCommandBus) -> None:
        """Register overwrites handler for same command type."""
        handler1 = _RecordingHandler()
        handler2 = _RecordingHandler()
        bus.register(SomeCommand, handler1)
        bus.register(SomeCommand, handler2)
        assert bus._handlers[SomeCommand] is handler2

    def test_dispatch_calls_registered_handler(self, bus: InMemoryCommandBus) -> None:
        """Dispatch calls the handler for the command type."""
        handler = _RecordingHandler()
        bus.register(SomeCommand, handler)

        command = SomeCommand(data="test")
        bus.dispatch(command)

        handler.assert_called_once_with(command)

    def test_dispatch_does_nothing_for_unknown_command(self, bus: InMemoryCommandBus) -> None:
        """Dispatch does nothing when no handler is registered."""
        command = SomeCommand(data="test")
        bus.dispatch(command)

    def test_dispatch_handles_multiple_commands(self, bus_with_handlers: InMemoryCommandBus) -> None:
        """Dispatch routes to correct handler based on command type."""
        handler1 = bus_with_handlers._handlers[SomeCommand]
        handler2 = bus_with_handlers._handlers[OtherCommand]

        bus_with_handlers.dispatch(SomeCommand(data="a"))
        bus_with_handlers.dispatch(OtherCommand(data="b"))

        handler1.assert_called_once()
        handler2.assert_called_once()

    def test_dispatch_passes_correct_command(self, bus: InMemoryCommandBus) -> None:
        """Dispatch passes the exact command object to handler."""
        handler = _RecordingHandler()
        bus.register(SomeCommand, handler)

        command = SomeCommand(data="payload123")
        bus.dispatch(command)

        handler.assert_called_once_with(command)


class SomeCommand:
    """Test command class."""

    def __init__(self, data: str) -> None:
        self.data = data


class OtherCommand:
    """Another test command class."""

    def __init__(self, data: str) -> None:
        self.data = data