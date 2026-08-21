"""GithubVerdictEventMapper — verdict to GitHub review event names."""

from typing import ClassVar

from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict


class GithubVerdictEventMapper:
    """Map a review verdict to the GitHub pull-request review event name.

    GitHub expects ``APPROVE`` (not ``APPROVED``) for approvals.
    """

    _VERDICT_TO_EVENT: ClassVar[dict[ReviewVerdict, str]] = {
        ReviewVerdict.APPROVED: "APPROVE",
        ReviewVerdict.CHANGES_REQUESTED: "REQUEST_CHANGES",
        ReviewVerdict.COMMENTED: "COMMENT",
    }

    def map(self, verdict: ReviewVerdict) -> str:
        """Return the GitHub review event name for *verdict*."""
        return self._VERDICT_TO_EVENT.get(verdict, "COMMENT")
