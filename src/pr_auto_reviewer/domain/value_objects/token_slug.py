"""TokenSlug — derived identifier from a token, safe for logging and file paths."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenSlug:
    """Derived identifier from a token, safe for logging and file paths.

    Exposes the last 8 characters of the token via ``value``, or ``"none"``
    when the token is empty/falsy.
    """

    token: str

    def __str__(self) -> str:
        return self.value

    @property
    def value(self) -> str:
        """Return the slug (last 8 chars, or ``"none"`` for empty tokens)."""
        return self.token[-8:] if self.token else "none"
