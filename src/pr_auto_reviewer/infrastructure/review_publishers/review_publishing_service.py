"""Support service for low-level platform review publishing operations."""

from __future__ import annotations

import logging
import re

from pr_auto_reviewer.domain.exceptions.review_publish_error import (
    ReviewPublishError,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.pull_request_diff import (
    PullRequestDiff,
)
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)

logger = logging.getLogger(__name__)


class ReviewPublishingService:
    """Handles low-level API operations for publishing reviews to git platforms.

    Composed by :class:`GithubReviewPublisher` to keep the publisher
    focused on orchestration while this service owns the API mechanics.
    """

    def __init__(
        self,
        client: GitPlatformHttpClient,
        owner_client: GitPlatformHttpClient,
    ) -> None:
        self._client = client
        self._owner_client = owner_client

    def verify_tokens(self, pr_id: PullRequestId) -> None:
        """Run preflight verification for both reviewer and owner tokens
        before publishing.  Wraps ``PreflightVerificationError`` as
        ``ReviewPublishError`` so the caller gets a uniform error type."""
        from pr_auto_reviewer.domain.exceptions.preflight_verification_error import (
            PreflightVerificationError,
        )
        try:
            self._client.verify_token_for_pr(pr_id)
        except PreflightVerificationError as exc:
            raise ReviewPublishError(
                f"Reviewer token preflight failed for {pr_id}: {exc}",
            ) from exc
        try:
            self._owner_client.verify_token_for_pr(pr_id)
        except PreflightVerificationError as exc:
            raise ReviewPublishError(
                f"Owner token preflight failed for {pr_id}: {exc}",
            ) from exc

    # -- item counting ------------------------------------------------------

    def count_existing_items(self, pr_id: PullRequestId) -> int:
        """Return count of existing reviews on this PR, used to offset
        issue numbers so new items don't reuse numbers from prior reviews."""
        try:
            reviews = self._client.get(
                f"/repos/{pr_id.repository}/pulls/{pr_id.number}/reviews",
                repo=pr_id.repository,
            )
            return len(reviews) if isinstance(reviews, list) else 0
        except Exception:
            return 0

    # -- comment publishing -------------------------------------------------

    def publish_comment(self, pr_id: PullRequestId, body: str) -> None:
        comments_path = f"/repos/{pr_id.repository}/issues/{pr_id.number}/comments"
        try:
            response = self._client.post(
                comments_path, {"body": body}, repo=pr_id.repository,
            )
            logger.debug("Comment posted: %s", response)
        except Exception as exc:
            logger.warning(
                "Failed to post comment on %s (non-fatal): %s", pr_id, exc,
            )

    # -- formal review publishing -------------------------------------------

    def publish_formal_review(
        self,
        pr_id: PullRequestId,
        verdict_event: str,
        body: str,
        blocking: list,
        *,
        platform: str = "github",
        official: bool = False,
        diff_headers: dict[str, str] | None = None,
        diff: PullRequestDiff | None = None,
    ) -> None:
        """Publish a formal PR review with optional inline comments."""
        reviews_path = (
            f"/repos/{pr_id.repository}/pulls/{pr_id.number}/reviews"
        )
        payload: dict[str, object] = {"event": verdict_event, "body": body}
        if official:
            payload["official"] = True

        try:
            if diff is not None and diff.head_sha is not None:
                payload["commit_id"] = str(diff.head_sha)
            else:
                pr_info = self._owner_client.get(
                    f"/repos/{pr_id.repository}/pulls/{pr_id.number}",
                    repo=pr_id.repository,
                )
                payload["commit_id"] = pr_info["head"]["sha"]
        except Exception as exc:
            raise ReviewPublishError(
                f"Failed to resolve commit_id for formal review of {pr_id}: {exc}",
            ) from exc

        try:
            if diff is not None and diff.diff_content is not None:
                diff_text = diff.diff_content
            else:
                diff_text = self._owner_client.get_raw(
                    f"/repos/{pr_id.repository}/pulls/{pr_id.number}.diff",
                    headers=diff_headers or {},
                    repo=pr_id.repository,
                )
            inline = self.build_inline_comments(
                diff_text, blocking, [], platform=platform,
            )
            if inline:
                payload["comments"] = inline
                logger.info(
                    "Added %d inline comments to formal review", len(inline),
                )
        except Exception as exc:
            logger.warning(
                "Failed to resolve inline comments for formal review: %s", exc,
            )

        try:
            self._client.post(
                reviews_path, payload, repo=pr_id.repository,
            )
        except Exception as exc:
            if "403" in str(exc):
                logger.error(
                    "Received 403 Forbidden when publishing review. "
                    "Ensure the token has required scopes and the reviewer "
                    "is authorized to post reviews on this repository."
                )
            raise ReviewPublishError(
                f"Failed to publish review for {pr_id}: {exc}",
            ) from exc

    # -- inline comment construction ----------------------------------------

    def build_inline_comments(
        self,
        diff_text: str,
        items: list,
        suggestions: list,
        *,
        platform: str = "github",
    ) -> list[dict]:
        """Build inline comment payloads from diff positions."""

        if platform == "forgejo":
            return self._build_forgejo_inline_comments(
                diff_text, items, suggestions,
            )
        return self._build_github_inline_comments(diff_text, items, suggestions)

    def _build_github_inline_comments(
        self, diff_text: str, items: list, suggestions: list,
    ) -> list[dict]:
        """Build GitHub-style inline comments using diff ``position``."""
        comments: list[dict] = []

        for item in items:
            pos_data = self.find_diff_position(
                diff_text, item.file_path, item.current_code,
            )
            if pos_data:
                comments.append(
                    {
                        "path": item.file_path,
                        "position": pos_data["position"],
                        "body": item.description,
                    }
                )

        for s in suggestions:
            s_file = s.file
            s_code = s.current_code
            if not s_file or not s_code:
                continue
            pos_data = self.find_diff_position(diff_text, s_file, s_code)
            if pos_data:
                s_body = s.description
                comments.append(
                    {
                        "path": s_file,
                        "position": pos_data["position"],
                        "body": s_body,
                    }
                )
        return comments

    def _build_forgejo_inline_comments(
        self, diff_text: str, items: list, suggestions: list,
    ) -> list[dict]:
        """Build Forgejo-style inline comments using ``old_position`` / ``new_position``."""
        comments: list[dict] = []

        for item in items:
            pos_data = self.find_diff_position(
                diff_text, item.file_path, item.current_code,
            )
            if pos_data:
                comments.append(
                    {
                        "path": item.file_path,
                        "body": item.description,
                        "old_position": pos_data["old_line"] or 0,
                        "new_position": pos_data["new_line"] or 0,
                    }
                )

        for s in suggestions:
            s_file = s.file
            s_code = s.current_code
            if not s_file or not s_code:
                continue
            pos_data = self.find_diff_position(diff_text, s_file, s_code)
            if pos_data:
                s_body = s.description
                comments.append(
                    {
                        "path": s_file,
                        "body": s_body,
                        "old_position": pos_data["old_line"] or 0,
                        "new_position": pos_data["new_line"] or 0,
                    }
                )
        return comments

    # -- diff position lookup -----------------------------------------------

    def find_diff_position(
        self,
        diff_text: str,
        file_path: str | None,
        current_code: str,
    ) -> dict[str, int | None] | None:
        """Locate a code snippet within a unified diff.

        Returns ``{"position": …, "old_line": …, "new_line": …}`` or
        ``None`` when the snippet cannot be found.

        All non-blank lines of *current_code* must match consecutive
        content lines in the diff.  Single-line snippets degenerate to
        the original behaviour.
        """
        if not file_path or not current_code:
            return None

        lines = diff_text.splitlines()
        in_target_file = False
        position = 0
        old_line = 0
        new_line = 0

        snippet_lines = [
            line.strip() for line in current_code.splitlines() if line.strip()
        ]
        if not snippet_lines:
            return None
        target_snippet = snippet_lines[0]

        for i, line in enumerate(lines):
            if line.startswith("diff --git"):
                in_target_file = file_path in line
                position = 0
                old_line = 0
                new_line = 0
                continue

            if not in_target_file:
                continue

            if line.startswith("@@"):
                m = re.search(r"-(\d+)(?:,\d+)? \+(\d+)", line)
                if m:
                    old_line = int(m.group(1)) - 1
                    new_line = int(m.group(2)) - 1
                position += 1
                continue

            if self._is_diff_metadata_line(line):
                continue

            if line.startswith(("--- ", "+++ ")):
                continue

            position += 1
            if line.startswith("-"):
                old_line += 1
                content = line[1:]
                if target_snippet in content:
                    if self._verify_remaining_snippet_lines(
                        lines, i + 1, snippet_lines[1:]
                    ):
                        return {
                            "position": position,
                            "old_line": old_line,
                            "new_line": None,
                        }
            elif line.startswith("+"):
                new_line += 1
                content = line[1:]
                if target_snippet in content:
                    if self._verify_remaining_snippet_lines(
                        lines, i + 1, snippet_lines[1:]
                    ):
                        return {
                            "position": position,
                            "old_line": None,
                            "new_line": new_line,
                        }
            else:
                old_line += 1
                new_line += 1
                content = line
                if target_snippet in content:
                    if self._verify_remaining_snippet_lines(
                        lines, i + 1, snippet_lines[1:]
                    ):
                        return {
                            "position": position,
                            "old_line": old_line,
                            "new_line": new_line,
                        }

        return None

    @staticmethod
    def _is_diff_metadata_line(line: str) -> bool:
        return line.startswith((
            "index ",
            "new file mode ",
            "deleted file mode ",
            "old mode ",
            "new mode ",
            "similarity index ",
            "dissimilarity index ",
            "rename from ",
            "rename to ",
            "copy from ",
            "copy to ",
        ))

    @staticmethod
    def _verify_remaining_snippet_lines(
        lines: list[str],
        start: int,
        remaining: list[str],
    ) -> bool:
        if not remaining:
            return True
        idx = 0
        for line in lines[start:]:
            if line.startswith("diff --git"):
                return False
            if line.startswith("@@"):
                continue
            if ReviewPublishingService._is_diff_metadata_line(line):
                continue
            if line.startswith(("--- ", "+++ ")):
                continue
            content = line[1:] if line[:1] in ("-", "+") else line
            if not content.strip():
                continue
            if remaining[idx] in content:
                idx += 1
                if idx == len(remaining):
                    return True
            else:
                return False
        return False
