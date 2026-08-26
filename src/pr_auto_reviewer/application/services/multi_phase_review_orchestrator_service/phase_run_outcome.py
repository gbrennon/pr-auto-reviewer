from ._shared import *


@dataclass(frozen=True)
class _PhaseRunOutcome:
    """Result of one full phase sequence plus its refutation evidence.

    ``dropped_findings`` counts model-reported findings that did not
    survive verification (synthetic filters, verifier refutation).  A
    zero-item review with a positive count is a *correct* refutation,
    not an under-examined diff — it must never trigger feedback
    pressure to manufacture findings.
    """

    review: CodeReview
    dropped_findings: int = 0

