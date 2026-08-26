from ._shared import *


@dataclass
class ProcessedReview:
    """Carrier for the output of the review-publication processor.

    The verdict *event* is the platform-specific mapping produced by the
    injected ``VerdictEventMapperPort`` (e.g. GitHub ``APPROVE``, Forgejo
    ``APPROVED``). No post-processing is applied by the caller.
    """

    verdict_event: str
    body: str
    blocking_items: list[ReviewItem]
    is_comment_only: bool

