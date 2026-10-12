from ._shared import *


@dataclass(kw_only=True)
class ProcessedReview:
    """Carrier for the output of the review-publication processor.

    The verdict *event* is the platform-specific mapping produced by the
    injected ``VerdictEventMapperPort`` (e.g. GitHub ``APPROVE``, Forgejo
    ``APPROVED``). No post-processing is applied by the caller.
    """
    blocking_items: list[ReviewItem]
    body: str
    comment_body: str | None = None
    is_comment_only: bool

    verdict_event: str

