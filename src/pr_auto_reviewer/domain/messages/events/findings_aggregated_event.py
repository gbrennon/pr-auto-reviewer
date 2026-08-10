"""FindingsAggregatedEvent — emitted when review findings are merged across phases."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.domain.value_objects.code_review import CodeReview


@dataclass(frozen=True)
class FindingsAggregatedEvent:
    """Emitted when findings from multiple phases are deduplicated and merged."""

    code_review: CodeReview
