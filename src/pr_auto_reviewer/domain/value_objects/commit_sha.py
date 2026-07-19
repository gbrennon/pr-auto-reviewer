"""CommitSha — represents a specific, immutable snapshot of code."""

from dataclasses import dataclass

from ..exceptions import InvalidCommitShaError

@dataclass(frozen=True)
class CommitSha:
    """Represents a specific, immutable snapshot of code.

    A SHA is content-addressed — it is its own identity.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value or not isinstance(self.value, str):
            raise InvalidCommitShaError(
                "CommitSha value must be a non-empty string"
            )

    def __str__(self) -> str:
        return self.value
