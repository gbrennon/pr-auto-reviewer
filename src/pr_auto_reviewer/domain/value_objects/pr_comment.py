"""PrComment — application-layer DTO for a comment on a pull request."""

from dataclasses import dataclass
from datetime import datetime

from .comment_id import CommentId


@dataclass(frozen=True)
class PrComment:
    """DTO carrying only what the service needs from a PR comment."""

    id: CommentId
    body: str
    created_at: datetime
