"""VerdictEventMapperPort — map a ReviewVerdict to a git-host review event string."""

from typing import Protocol

from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict


class VerdictEventMapperPort(Protocol):
    """Map a review verdict to the publishing git host's review event name.

    Each git host uses a different event vocabulary (e.g. GitHub ``APPROVE``
    vs Forgejo ``APPROVED``), so the mapping is an outbound port implemented
    by infrastructure adapters per platform.
    """

    def map(self, verdict: ReviewVerdict) -> str: ...
