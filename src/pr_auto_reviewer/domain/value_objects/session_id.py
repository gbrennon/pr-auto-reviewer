"""Session identity value object."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from ..exceptions.invalid_session_id_error import InvalidSessionIdError


@dataclass(frozen=True)
class SessionId:
    """A safe, non-empty session identifier."""

    value: str

    def __post_init__(self) -> None:
        if not self.value or re.fullmatch(r"[a-zA-Z0-9_.-]+", self.value) is None:
            raise InvalidSessionIdError(
                "session id must be non-empty and contain only letters, numbers, _, -, or ."
            )

    @classmethod
    def generate(cls, prefix: str = "session") -> SessionId:
        """Generate a timestamped identifier with a random suffix."""
        value = f"{prefix}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        return cls(value)

    def __str__(self) -> str:
        return self.value
