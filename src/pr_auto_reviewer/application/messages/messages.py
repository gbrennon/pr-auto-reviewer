"""Pure domain functions to build human-readable comment messages."""

from ...domain.entities.issue import Issue
from ...domain.entities.review_item import ReviewItem


def invalid_items_message(
    invalid: list[int], available: list[ReviewItem]
) -> str:
    invalid_list = ", ".join(f"#{n}" for n in invalid)
    available_list = "\n".join(
        f"- #{item.number}: {item.description[:60]}..."
        for item in available
    )
    return (
        f"Could not find review items: {invalid_list}.\n\n"
        f"Available items:\n{available_list}"
    )


def issues_created_message(issues: list[Issue]) -> str:
    links = "\n".join(f"- #{i.id}: {i.title}" for i in issues)
    return f"Created {len(issues)} issue(s):\n\n{links}"
