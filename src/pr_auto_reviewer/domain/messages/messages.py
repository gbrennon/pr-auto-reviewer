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

def issues_created_message(issues: Sequence[Issue]) -> str:
    links = "\n".join(f"- #{i.id}: {i.title}" for i in issues)
    return f"Created {len(issues)} issue(s):\n\n{links}"
