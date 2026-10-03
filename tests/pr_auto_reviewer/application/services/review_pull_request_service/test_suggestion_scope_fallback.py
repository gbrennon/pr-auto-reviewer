from pathlib import Path
from unittest.mock import MagicMock

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.application.services.review_pull_request_service import (
    ReviewPullRequestService,
)
from pr_auto_reviewer.domain.messages.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId


class TestSuggestionScopeFallback:
    """Single-turn publication applies suggestion scope evidence."""

    def test_single_turn_review_publishes_only_evidenced_suggestions(
        self, tmp_path: Path,
    ) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        source_directory = tmp_path / "src"
        source_directory.mkdir()
        (source_directory / "config.py").write_text("CONFIG = {}\n")
        (source_directory / "other.py").write_text("OTHER = {}\n")
        diff = PullRequestDiff(
            pr_id=PullRequestId(repository="owner/repo", number=42),
            head_sha=CommitSha(value="abc123"),
            diff_content=(
                "diff --git a/pyproject.toml b/pyproject.toml\n"
                "--- a/pyproject.toml\n"
                "+++ b/pyproject.toml\n"
                "@@ -1 +1 @@\n"
                "+[project]\n"
            ),
            file_contents={"pyproject.toml": "[project]\n"},
            clone_path=tmp_path,
        )
        related = ReviewItem(
            severity=ItemSeverity.INFO,
            category=IssueCategory.GENERAL,
            file_path="src/config.py",
            description="The pyproject.toml configuration is loaded here.",
            id="related",
        )
        unrelated = ReviewItem(
            severity=ItemSeverity.INFO,
            category=IssueCategory.GENERAL,
            file_path="src/other.py",
            description="Centralize this module's settings boundary.",
            id="unrelated",
        )
        fileless = ReviewItem(
            severity=ItemSeverity.INFO,
            category=IssueCategory.GENERAL,
            file_path="",
            description="Adopt one dependency direction across the repository.",
            id="fileless",
        )
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            reason="Review completed.",
            summary="No blocking findings.",
            suggestions=[related, unrelated, fileless],
            model_used="test",
        )
        repository = MagicMock()
        repository.find.return_value = None
        changeset_fetcher = MagicMock()
        changeset_fetcher.fetch.return_value = diff
        context_factory = MagicMock()
        llm_review = MagicMock()
        llm_review.review_prompt.return_value = review
        publisher = MagicMock()
        command = ReviewPullRequestCommand(
            pr_id=diff.pr_id,
            head_sha=diff.head_sha,
            title="Update project metadata",
        )

        ReviewPullRequestService(
            repository,
            changeset_fetcher,
            context_factory,
            llm_review,
            publisher,
        ).execute(command)

        published = publisher.publish.call_args.args[1]
        assert [item.id for item in published.suggestions] == ["related", "fileless"]
