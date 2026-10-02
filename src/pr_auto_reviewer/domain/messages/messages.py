"""Pure domain functions to build human-readable comment messages."""

from collections.abc import Sequence
from ..entities.issue import Issue
from ..entities.review_item import ReviewItem


def invalid_items_message(
    invalid: Sequence[str | int], available: Sequence[ReviewItem]
) -> str:
    invalid_list = ", ".join(f"#{n}" for n in invalid)
    available_list = "\n".join(
        f"- #{item.id}: {item.description[:60]}..."
        for item in available
    )
    return (
        f"Could not find review items: {invalid_list}.\n\n"
        f"Available items:\n{available_list}"
    )

def issues_created_message(
    issues: Sequence[Issue], review_items: Sequence[ReviewItem]
) -> str:
    """Build a human-readable comment summarizing created issues."""
    items_by_id = {item.id: item for item in review_items}
    lines = "\n".join(
        _created_issue_line(issue, items_by_id.get(issue.source_item_id))
        for issue in issues
    )
    return f"Created {len(issues)} issue(s):\n\n{lines}"


def _created_issue_line(issue: Issue, item: ReviewItem | None) -> str:
    """Format one issue line with its source review item classification and status."""
    header = f"- #{issue.id}: {issue.title}"
    if item is None:
        return (
            f"{header}\n"
            f"  - review item `{issue.source_item_id}` "
            "— status: unknown (no longer in the latest review)"
        )
    blocking_label = "blocking" if item.is_blocking else "non-blocking"
    relevance = "still relevant" if item.is_open else "no longer relevant"
    return (
        f"{header}\n"
        f"  - review item `{issue.source_item_id}` "
        f"({item.severity.value} {item.category.value}, {blocking_label}) "
        f"— status: {item.status} ({relevance})"
    )
