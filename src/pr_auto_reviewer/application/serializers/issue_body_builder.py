"""IssueBodyBuilder — pure domain service to build issue title and body."""

from ...domain.entities.review_item import ReviewItem
from ...domain.value_objects.pull_request_id import PullRequestId


class IssueBodyBuilder:
    """Produces (title, body) for a tracker issue from a ReviewItem.
    The template is a domain rule — no platform formatting leaks in."""

    def build(
        self, pr_id: PullRequestId, item: ReviewItem
    ) -> tuple[str, str]:
        title = (
            f"[{item.severity.upper()}] {item.category}: "
            f"{IssueBodyBuilder._truncate_on_boundary(item.description, 80)}"
        )

        location = (
            f"`{item.file_path}`" if item.file_path else "_(no specific file)_"
        )

        item_ref = item.id
        body_parts = [
            f"## Review Item {item_ref} from {pr_id}\n",
            f"- **Severity:** {item.severity.upper()}",
            f"- **Category:** {item.category}",
            f"- **File:** {location}\n",
            f"{item.description}\n",
        ]

        if item.current_code:
            body_parts.append(
                "### Current Code\n```\n" + item.current_code + "\n```\n"
            )

        if item.suggested_fix:
            body_parts.append(
                "### Suggested Fix\n```\n" + item.suggested_fix + "\n```\n"
            )

        body = "\n".join(body_parts)

        return title, body

    @staticmethod
    def _truncate_on_boundary(text: str, limit: int) -> str:
        """Clip *text* to *limit* chars at a sentence or word edge.

        A hard mid-word cut produced published titles ending in
        fragments like "…eliminates r".  The cut lands on the last
        sentence end within the limit, else on the last word
        boundary, with an ellipsis marker when anything was removed.
        """
        if len(text) <= limit:
            return text
        window = text[:limit]
        sentence_end = max(
            window.rfind(marker)
            for marker in (". ", "! ", "? ")
        )
        if sentence_end > limit // 2:
            return window[:sentence_end + 1].rstrip()
        word_end = window.rfind(" ")
        if word_end > limit // 2:
            return window[:word_end].rstrip() + "…"
        return window.rstrip() + "…"
