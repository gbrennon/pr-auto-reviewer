from __future__ import annotations

from enum import StrEnum

from textual.events import Key
from textual.widgets import Input


class NavigationMode(StrEnum):
    """Keyboard navigation modes supported by the dashboard inputs."""

    ARROWS = "arrows"
    VIM = "vim"
    EMACS = "emacs"

    @classmethod
    def parse(cls, value: str | None) -> NavigationMode:
        """Parse a configured mode, defaulting to conventional arrow keys."""
        normalized = (value or cls.ARROWS).strip().lower()
        try:
            return cls(normalized)
        except ValueError:
            return cls.ARROWS


class NavigationInput(Input):
    """Text input with explicit dashboard navigation semantics."""

    def __init__(self, *args: object, mode: NavigationMode = NavigationMode.ARROWS, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self._navigation_mode = mode
        self._vim_insert_mode = False

    @property
    def navigation_mode(self) -> NavigationMode:
        """Return the active keyboard navigation mode."""
        return self._navigation_mode

    def set_navigation_mode(self, mode: NavigationMode) -> None:
        """Change the keyboard navigation mode and reset Vim insert state."""
        self._navigation_mode = mode
        self._vim_insert_mode = False

    async def _on_key(self, event: Key) -> None:
        if self._navigation_mode is NavigationMode.ARROWS:
            await super()._on_key(event)
            return
        if self._navigation_mode is NavigationMode.EMACS:
            if event.key == "ctrl+b":
                self.action_cursor_left()
                self._consume(event)
                return
            if event.key == "ctrl+f":
                self.action_cursor_right()
                self._consume(event)
                return
            if event.key == "ctrl+n":
                self.screen.focus_next(Input)
                self._consume(event)
                return
            if event.key == "ctrl+p":
                self.screen.focus_previous(Input)
                self._consume(event)
                return
            await super()._on_key(event)
            return
        if event.key == "escape":
            self._vim_insert_mode = False
            self._consume(event)
            return
        if not self._vim_insert_mode:
            if event.key == "i":
                self._vim_insert_mode = True
            elif event.key == "h":
                self.action_cursor_left()
            elif event.key == "l":
                self.action_cursor_right()
            elif event.key == "j":
                self.screen.focus_next(Input)
            elif event.key == "k":
                self.screen.focus_previous(Input)
            self._consume(event)
            return
        if event.key in {"left", "right", "up", "down"}:
            self._consume(event)
            return
        await super()._on_key(event)

    @staticmethod
    def _consume(event: Key) -> None:
        event.stop()
        event.prevent_default()
