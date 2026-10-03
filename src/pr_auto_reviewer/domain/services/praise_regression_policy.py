"""PraiseRegressionPolicy — turn lost prior praise into forward-looking suggestions."""

from __future__ import annotations

from ..entities.review_item import ReviewItem
from ..value_objects.issue_category import IssueCategory
from ..value_objects.item_severity import ItemSeverity

class PraiseRegressionPolicy:
    """Derive suggestions from prior praise the current review no longer affirms.

    A quality praised in an earlier review that is absent from the current
    review's praise is treated as a regression worth surfacing — always as a
    non-blocking suggestion, never as an issue. Each lost praise becomes a
    single INFO/GENERAL suggestion that names the quality and explains it is
    no longer present.

    Matching is deterministic: prior and current praise are compared by
    ``(file_path, description)`` after normalization. Previously emitted
    regression suggestions are skipped so the same loss is not restated on
    every subsequent run.
    """

    _PREAMBLE = (
        "This pull request previously received praise for "
    )
    _EPILOGUE = (
        ", but that quality is no longer present in the current revision."
    )

    def regressions(
        self,
        prior_praise: list[ReviewItem],
        current_praise: list[ReviewItem],
        existing_suggestions: list[ReviewItem],
    ) -> list[ReviewItem]:
        """Return new suggestion items for prior praise no longer affirmed."""
        affirmed = {self._praise_key(p) for p in current_praise}
        already_suggested = {self._text_key(s) for s in existing_suggestions}
        return [
            self._as_suggestion(praise)
            for praise in self._lost_praise(prior_praise, affirmed)
            if self._text_key_for(praise.file_path, self._describe(praise))
            not in already_suggested
        ]

    def _lost_praise(
        self,
        prior_praise: list[ReviewItem],
        affirmed: set[tuple[str, str]],
    ) -> list[ReviewItem]:
        """Return prior praise not affirmed now, deduplicated by content."""
        seen: set[tuple[str, str]] = set()
        lost: list[ReviewItem] = []
        for praise in prior_praise:
            key = self._praise_key(praise)
            if key in affirmed or key in seen:
                continue
            seen.add(key)
            lost.append(praise)
        return lost

    def _as_suggestion(self, praise: ReviewItem) -> ReviewItem:
        return ReviewItem(
            severity=ItemSeverity.INFO,
            category=IssueCategory.GENERAL,
            file_path=praise.file_path,
            description=self._describe(praise),
        )

    def _describe(self, praise: ReviewItem) -> str:
        quality = praise.description.strip()
        return f'{self._PREAMBLE}"{quality}"{self._EPILOGUE}'

    def _praise_key(self, item: ReviewItem) -> tuple[str, str]:
        return (
            (item.file_path or "").strip(),
            item.description.strip().lower(),
        )

    def _text_key(self, item: ReviewItem) -> tuple[str, str]:
        return self._text_key_for(item.file_path, item.description)

    def _text_key_for(self, file_path: str | None, description: str) -> tuple[str, str]:
        return ((file_path or "").strip(), description.strip())
