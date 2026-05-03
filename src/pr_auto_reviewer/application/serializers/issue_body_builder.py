"""IssueBodyBuilder — pure domain service to build issue title and body."""

from ...domain.value_objects.pull_request_id import PullRequestId
from ...domain.entities.review_item import ReviewItem


class IssueBodyBuilder:
    """Produces (title, body) for a tracker issue from a ReviewItem.
    The template is a domain rule — no platform formatting leaks in."""

    def build(
        self, pr_id: PullRequestId, item: ReviewItem
    ) -> tuple[str, str]:
        title = f"[{item.severity.upper()}] {item.category}: {item.description[:80]}"

        location = (
            f"`{item.file_path}`" if item.file_path else "_(no specific file)_"
        )

        body = (
            f"## Review Item #{item.number} from {pr_id}\n\n"
            f"- **Severity:** {item.severity.upper()}\n"
            f"- **Category:** {item.category}\n"
            f"- **File:** {location}\n\n"
            f"{item.description}\n"
        )

        return title, body
