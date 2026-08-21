"""ForgejoVerdictEventMapper — verdict to Forgejo/Codeberg review event names."""

from typing import ClassVar

from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict


class ForgejoVerdictEventMapper:
    """Map a review verdict to the Forgejo/Codeberg pull-request review event name.

    Forgejo expects ``APPROVED`` (not ``APPROVE``) for approvals.
    """

    _VERDICT_TO_EVENT: ClassVar[dict[ReviewVerdict, str]] = {
        ReviewVerdict.APPROVED: "APPROVED",
        ReviewVerdict.CHANGES_REQUESTED: "REQUEST_CHANGES",
        ReviewVerdict.COMMENTED: "COMMENT",
    }

    def map(self, verdict: ReviewVerdict) -> str:
        """Return the Forgejo review event name for *verdict*."""
        return self._VERDICT_TO_EVENT.get(verdict, "COMMENT")
