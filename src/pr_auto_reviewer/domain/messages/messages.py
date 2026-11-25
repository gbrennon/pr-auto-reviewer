"""Pure domain functions to build human-readable comment messages."""

from collections.abc import Sequence

from ..entities.issue import Issue
from ..entities.review_item import ReviewItem
from ..value_objects.issue_command_action import IssueCommandAction

def invalid_items_message(
    invalid: Sequence[str | int], available: Sequence[ReviewItem]
) -> str:
    invalid_list = ", ".join(f"#{n}" for n in invalid)
    available_list = "\n".join(
        f"- {_command_item_label(item)}: {item.description[:60]}..."
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

def dismissed_items_message(
    item_ids: Sequence[str], review_items: Sequence[ReviewItem],
) -> str:
    """Build an acknowledgement with each dismissed item's classification."""
    items_by_id = {item.id: item for item in review_items}
    details = ", ".join(
        _command_item_label(items_by_id[item_id])
        for item_id in item_ids
        if item_id in items_by_id
    )
    return f"Dismissed {len(item_ids)} non-blocking review item(s): {details}"


def rejected_command_items_message(
    action: IssueCommandAction,
    item_ids: Sequence[str],
    review_items: Sequence[ReviewItem],
) -> str:
    """Explain why command IDs were not eligible for automation."""
    action_name = (
        "create tracker issues"
        if action is IssueCommandAction.CREATE_ISSUE
        else "dismiss review items"
    )
    items_by_id = {item.id: item for item in review_items}
    details = ", ".join(
        _command_item_label_for_id(item_id, items_by_id)
        for item_id in item_ids
    )
    return (
        f"Cannot {action_name} for: {details}. "
        "Only open non-blocking review items are eligible; "
        "blocking findings must be handled through code changes and formal review."
    )

def issue_creation_failed_message(
    item_ids: Sequence[str],
    review_items: Sequence[ReviewItem],
    *,
    reason: str = "tracker issue creation failed",
) -> str:
    """Explain that a tracker issue command was finalized after failure."""
    items_by_id = {item.id: item for item in review_items}
    details = ", ".join(
        _command_item_label_for_id(item_id, items_by_id)
        for item_id in item_ids
    )
    return (
        f"Could not create tracker issue(s) for: {details}.\n\n"
        f"Reason: {reason}.\n\n"
        "The command was recorded and will not be retried automatically. "
        "Create the issue manually after resolving the tracker problem."
    )


def _command_item_label(item: ReviewItem) -> str:
    """Format an item ID with severity, category, and blocking classification."""
    classification = "[BLOCKING]" if item.is_blocking else "[NON-BLOCKING]"
    return (
        f"`{item.id}` {classification} ({item.severity.value} "
        f"{item.category.value}; status: {item.status.value})"
    )

def _command_item_label_for_id(
    item_id: str, items_by_id: dict[str, ReviewItem],
) -> str:
    item = items_by_id.get(item_id)
    if item is None:
        return f"`{item_id}` [UNKNOWN] (classification unavailable)"
    return _command_item_label(item)


def _created_issue_line(issue: Issue, item: ReviewItem | None) -> str:
    """Format one issue line with its source review item classification and status."""
    header = f"- #{issue.id}: {issue.title}"
    if item is None:
        return (
            f"{header}\n"
            f"  - review item `{issue.source_item_id}` [UNKNOWN] "
            "— status: unknown (no longer in the latest review)"
        )
    classification = "[BLOCKING]" if item.is_blocking else "[NON-BLOCKING]"
    relevance = "still relevant" if item.is_open else "no longer relevant"
    return (
        f"{header}\n"
        f"  - review item `{issue.source_item_id}` {classification} "
        f"({item.severity.value} {item.category.value}) "
        f"— status: {item.status.value} ({relevance})"
    )
