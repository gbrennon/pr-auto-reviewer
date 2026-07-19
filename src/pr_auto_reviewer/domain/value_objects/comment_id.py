"""CommentId — opaque identifier for a comment on a pull request."""

from dataclasses import dataclass

from ..exceptions import InvalidCommentIdError

@dataclass(frozen=True)
class CommentId:
    """Opaque identifier for a comment on a pull request.

    An identifier treated as a value for idempotency tracking — it never changes.
    """

    value: str

    def __post_init__(self) -> None:
        if not self.value or not isinstance(self.value, str):
            raise InvalidCommentIdError(
                "CommentId value must be a non-empty string"
            )

    def __str__(self) -> str:
        return self.value
