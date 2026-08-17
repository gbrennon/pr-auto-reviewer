"""Application-layer tests for ReviewPullRequestService.

Uses injected mocks (not hand-written stubs) for outbound ports.
All domain objects are real — PullRequest, CodeReview, PullRequestDiff.
Diff fixtures come from tests/fixtures/diffs/.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from pr_auto_reviewer.application.services import ReviewPullRequestService
from pr_auto_reviewer.domain import (
    CodeReview,
    CommitSha,
    EmptyDiffError,
    PullRequest,
    PullRequestDiff,
    PullRequestId,
    ReviewVerdict,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.messages.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "diffs"


def _pr_id(repo="owner/repo", num=42):
    return PullRequestId(repository=repo, number=num)


def _sha(v="abc123"):
    return CommitSha(value=v)


def _cmd(pr_id=None, sha=None):
    return ReviewPullRequestCommand(
        pr_id=pr_id or _pr_id(),
        head_sha=sha or _sha(),
        title="Add feature X",
    )


def _diff_fixture(pr_id, sha):
    return PullRequestDiff(
        pr_id=pr_id,
        head_sha=sha,
        diff_content=(FIXTURES / "sample-service.diff").read_text(),
        file_contents={"src/main.py": "def hello(): pass\n"},
    )


def _review(verdict=ReviewVerdict.APPROVED):
    return CodeReview(verdict=verdict, summary="Looks good", model_used="test")


def _pr(pr_id, sha):
    return PullRequest(id=pr_id, title="Add feature X", head_sha=sha)


class TestReviewPullRequestService:
    def test_new_pr_full_flow(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        cmd = _cmd()
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        mock_llm_review.review_prompt.return_value = _review(
            ReviewVerdict.APPROVED
        )

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        mock_pr_repository.find.assert_called_once_with(cmd.pr_id)
        mock_changeset_fetcher.fetch.assert_called_once_with(
            cmd.pr_id, cmd.head_sha
        )
        mock_review_context_factory.build.assert_called_once()
        mock_llm_review.review_prompt.assert_called_once()
        mock_review_publisher.publish.assert_called_once()
        args, _ = mock_review_publisher.publish.call_args
        assert args[2] is not None, "diff should be passed to publisher"
        mock_pr_repository.save.assert_called_once()
        assert mock_pr_repository.save.call_args.args[0].head_sha == cmd.head_sha

    def test_already_reviewed_sha_skips_review(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        cmd = _cmd()
        existing = _pr(cmd.pr_id, cmd.head_sha)
        existing = existing.add_review(_review(), cmd.head_sha)
        mock_pr_repository.find.return_value = existing

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        mock_changeset_fetcher.fetch.assert_not_called()
        mock_review_context_factory.build.assert_not_called()
        mock_llm_review.review_prompt.assert_not_called()
        mock_review_publisher.publish.assert_not_called()
        mock_pr_repository.save.assert_called_once()

    def test_force_bypasses_idempotency_guard(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        sha = _sha()
        cmd = ReviewPullRequestCommand(
            pr_id=_pr_id(),
            head_sha=sha,
            title="Add feature X",
            force=True,
        )
        existing = _pr(cmd.pr_id, sha)
        existing = existing.add_review(_review(), sha)
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        mock_pr_repository.find.return_value = existing
        mock_changeset_fetcher.fetch.return_value = diff
        mock_llm_review.review_prompt.return_value = _review(
            ReviewVerdict.APPROVED
        )

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        mock_changeset_fetcher.fetch.assert_called_once()
        mock_review_context_factory.build.assert_called_once()
        mock_llm_review.review_prompt.assert_called_once()
        mock_review_publisher.publish.assert_called_once()
        mock_pr_repository.save.assert_called_once()

    def test_re_review_triggered_when_review_requested(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        sha = _sha()
        cmd = ReviewPullRequestCommand(
            pr_id=_pr_id(),
            head_sha=sha,
            title="Add feature X",
            review_requested=True,
        )
        existing = PullRequest(
            id=cmd.pr_id, title=cmd.title, head_sha=sha,
        )
        existing = existing.add_review(_review(), sha)
        mock_pr_repository.find.return_value = existing
        mock_changeset_fetcher.fetch.return_value = _diff_fixture(
            cmd.pr_id, cmd.head_sha
        )
        mock_llm_review.review_prompt.return_value = _review(
            ReviewVerdict.APPROVED
        )

        ReviewPullRequestService(
            mock_pr_repository, mock_changeset_fetcher,
            mock_review_context_factory, mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        mock_changeset_fetcher.fetch.assert_called_once()
        mock_review_context_factory.build.assert_called_once()
        mock_llm_review.review_prompt.assert_called_once()
        mock_review_publisher.publish.assert_called_once()
        mock_pr_repository.save.assert_called_once()

    def test_no_re_review_when_review_requested_false(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        sha = _sha()
        cmd = ReviewPullRequestCommand(
            pr_id=_pr_id(),
            head_sha=sha,
            title="Add feature X",
            review_requested=False,
        )
        existing = PullRequest(
            id=cmd.pr_id, title=cmd.title, head_sha=sha,
        )
        existing = existing.add_review(_review(), sha)
        mock_pr_repository.find.return_value = existing

        ReviewPullRequestService(
            mock_pr_repository, mock_changeset_fetcher,
            mock_review_context_factory, mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        mock_changeset_fetcher.fetch.assert_not_called()
        mock_review_context_factory.build.assert_not_called()
        mock_llm_review.review_prompt.assert_not_called()
        mock_review_publisher.publish.assert_not_called()
        mock_pr_repository.save.assert_called_once()

    def test_empty_diff_raises(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = PullRequestDiff(
            pr_id=_pr_id(),
            head_sha=_sha(),
            diff_content="   \n ",
        )
        svc = ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        )
        with pytest.raises(EmptyDiffError):
            svc.execute(_cmd())

    def test_existing_pr_new_sha_runs_full_flow(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        old, new = _sha("old111"), _sha("new222")
        cmd = _cmd(sha=new)
        existing = _pr(cmd.pr_id, old)
        existing = existing.add_review(_review(ReviewVerdict.COMMENTED), old)
        mock_pr_repository.find.return_value = existing
        mock_changeset_fetcher.fetch.return_value = _diff_fixture(
            cmd.pr_id, cmd.head_sha
        )
        mock_llm_review.review_prompt.return_value = _review(
            ReviewVerdict.APPROVED
        )

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        mock_changeset_fetcher.fetch.assert_called_once()
        mock_review_context_factory.build.assert_called_once()
        mock_llm_review.review_prompt.assert_called_once()
        mock_review_publisher.publish.assert_called_once()

    def test_debug_logs_review_complete_summary(
        self, caplog, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        cmd = _cmd()
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        mock_llm_review.review_prompt.return_value = _review(
            ReviewVerdict.CHANGES_REQUESTED
        )

        caplog.set_level(logging.DEBUG)
        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        summaries = [
            r.message for r in caplog.records if "REVIEW COMPLETE" in r.message
        ]
        assert len(summaries) == 1
        assert "verdict=changes_requested" in summaries[0]
        assert "items=0" in summaries[0]
        assert "summary='Looks good'" in summaries[0]

    def test_review_complete_summary_not_logged_at_info(
        self, caplog, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        cmd = _cmd()
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        mock_llm_review.review_prompt.return_value = _review()

        caplog.set_level(logging.INFO)
        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        summaries = [
            r.message for r in caplog.records if "REVIEW COMPLETE" in r.message
        ]
        assert len(summaries) == 0

    def test_review_complete_summary_not_logged_when_skipped(
        self, caplog, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        cmd = _cmd()
        existing = _pr(cmd.pr_id, cmd.head_sha)
        existing = existing.add_review(_review(), cmd.head_sha)
        mock_pr_repository.find.return_value = existing

        caplog.set_level(logging.DEBUG)
        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        summaries = [
            r.message for r in caplog.records if "REVIEW COMPLETE" in r.message
        ]
        assert len(summaries) == 0

    def test_prompt_from_factory_is_sent_to_llm(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        cmd = _cmd()
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        prompt = ComposedPrompt(
            content="You are a code reviewer.\n\nReview this diff:\n+code",
            fragments_used=["solid", "python-errors"],
            total_tokens=100,
        )
        mock_review_context_factory.build.return_value = prompt
        mock_llm_review.review_prompt.return_value = _review()

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        mock_review_context_factory.build.assert_called_once()
        args, _ = mock_llm_review.review_prompt.call_args
        assert args[0] is prompt

    def test_factory_receives_diff_in_build_call(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        cmd = _cmd()
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        mock_llm_review.review_prompt.return_value = _review()

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        mock_review_context_factory.build.assert_called_once()
        args, _ = mock_review_context_factory.build.call_args
        pr_id_arg, build_diff = args[0], args[1]
        assert build_diff is diff
        assert "diff --git" in build_diff.diff_content
        assert pr_id_arg == cmd.pr_id

    def test_adds_concrete_finding_for_noisy_info_log_when_llm_misses_it(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        cmd = _cmd()
        diff = PullRequestDiff(
            pr_id=cmd.pr_id,
            head_sha=cmd.head_sha,
            diff_content=(
                "diff --git a/src/client.py b/src/client.py\n"
                "+++ b/src/client.py\n"
                "@@ -1,2 +1,3 @@\n"
                '+        logger.info("GET %s params=%s", url, params)\n'
            ),
        )
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        mock_llm_review.review_prompt.return_value = _review(
            ReviewVerdict.APPROVED
        )

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        _, kwargs = mock_review_publisher.publish.call_args
        review = kwargs.get("review") or mock_review_publisher.publish.call_args.args[1]
        assert len(review.items) == 1
        assert review.items[0].file_path == "src/client.py"
        assert review.items[0].current_code == (
            '        logger.info("GET %s params=%s", url, params)'
        )
        assert review.items[0].suggested_fix == (
            '        logger.debug("GET %s params=%s", url, params)'
        )

    def test_adds_noisy_log_findings_before_llm_findings(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        cmd = _cmd()
        diff = PullRequestDiff(
            pr_id=cmd.pr_id,
            head_sha=cmd.head_sha,
            diff_content=(
                "diff --git a/src/client.py b/src/client.py\n"
                "+++ b/src/client.py\n"
                "@@ -1,2 +1,3 @@\n"
                '+        logger.info("GET %s params=%s", url, params)\n'
            ),
        )
        llm_review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            summary="LLM finding",
            items=[
                ReviewItem(id="id-1",
                    severity="minor",
                    category="quality",
                    file_path="src/other.py",
                    description="existing",
                    current_code="x = 1",
                    suggested_fix="x = 2",
                )
            ],
        )
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        mock_llm_review.review_prompt.return_value = llm_review

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        args, _ = mock_review_publisher.publish.call_args
        review = args[1]
        assert len(review.items) == 2
        assert review.items[0].file_path == "src/client.py"
        assert review.items[1].file_path == "src/other.py"

    def test_skips_log_info_without_noisy_marker(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        """A logger.info() line without noisy markers does not produce a finding."""
        cmd = _cmd()
        diff = PullRequestDiff(
            pr_id=cmd.pr_id,
            head_sha=cmd.head_sha,
            diff_content=(
                "diff --git a/src/client.py b/src/client.py\n"
                "+++ b/src/client.py\n"
                "@@ -1,2 +1,3 @@\n"
                '+        logger.info("processing complete without markers")\n'
            ),
        )
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        mock_llm_review.review_prompt.return_value = _review(
            ReviewVerdict.APPROVED
        )

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        args, _ = mock_review_publisher.publish.call_args
        review = args[1]
        assert len(review.items) == 0

    def test_limits_noisy_log_findings_to_five(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        """Noisy log detection caps at 5 findings."""
        cmd = _cmd()
        diff = PullRequestDiff(
            pr_id=cmd.pr_id,
            head_sha=cmd.head_sha,
            diff_content=(
                "diff --git a/src/app.py b/src/app.py\n"
                "+++ b/src/app.py\n"
                "@@ -1,10 +1,10 @@\n"
                '+        logger.info("GET %s", url)\n'
                '+        logger.info("POST %s", url)\n'
                '+        logger.info("return: %s", result)\n'
                '+        logger.info("keys=%s", data.keys())\n'
                '+        logger.info("chars=%s", text)\n'
                '+        logger.info("tokens=%s", tokens)\n'
            ),
        )
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        mock_llm_review.review_prompt.return_value = _review(
            ReviewVerdict.APPROVED
        )

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        args, _ = mock_review_publisher.publish.call_args
        review = args[1]
        assert len(review.items) == 5

    def test_preserves_changes_requested_verdict_when_adding_deterministic_findings(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        """LLM returns CHANGES_REQUESTED + diff triggers noisy-log detection
        → verdict stays CHANGES_REQUESTED after _add_deterministic_findings."""
        cmd = _cmd()
        diff = PullRequestDiff(
            pr_id=cmd.pr_id,
            head_sha=cmd.head_sha,
            diff_content=(
                "diff --git a/src/client.py b/src/client.py\n"
                "+++ b/src/client.py\n"
                "@@ -1,2 +1,3 @@\n"
                '+        logger.info("GET %s params=%s", url, params)\n'
            ),
        )
        llm_review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            summary="Needs work",
            items=[
                ReviewItem(id="id-1",
                    severity="blocker",
                    category="bug",
                    file_path="src/other.py",
                    description="Null dereference",
                    current_code="x = None; x.foo()",
                    suggested_fix="guard with if x is not None",
                ),
                ReviewItem(id="id-2",
                    severity="major",
                    category="quality",
                    file_path="src/other.py",
                    description="Magic number",
                    current_code="sleep(300)",
                    suggested_fix="sleep(TIMEOUT)",
                ),
                ReviewItem(id="id-3",
                    severity="minor",
                    category="style",
                    file_path="src/other.py",
                    description="Bad variable name",
                    current_code="x = 1",
                    suggested_fix="count = 1",
                ),
                ReviewItem(id="id-4",
                    severity="minor",
                    category="quality",
                    file_path="src/other.py",
                    description="Unused import",
                    current_code="import os",
                    suggested_fix="",
                ),
            ],
        )
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        mock_llm_review.review_prompt.return_value = llm_review

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        args, _ = mock_review_publisher.publish.call_args
        review = args[1]
        assert review.verdict == ReviewVerdict.CHANGES_REQUESTED, (
            f"Expected CHANGES_REQUESTED but got {review.verdict}"
        )
        assert len(review.items) == 5, (
            f"Expected 5 items (4 LLM + 1 deterministic), got {len(review.items)}"
        )


class TestReviewPullRequestServiceTokenVerifier:
    def test_execute_with_token_verifier(
        self, mock_token_verifier: MagicMock,
        mock_pr_repository: MagicMock,
        mock_changeset_fetcher: MagicMock,
        mock_review_context_factory: MagicMock,
        mock_llm_review: MagicMock,
        mock_review_publisher: MagicMock,
    ):
        cmd = _cmd()
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = _diff_fixture(cmd.pr_id, cmd.head_sha)
        mock_llm_review.review_prompt.return_value = _review(ReviewVerdict.APPROVED)

        service = ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
            token_verifier=mock_token_verifier,
        )

        service.execute(cmd)

        mock_token_verifier.verify.assert_called_with(cmd.pr_id)

    def test_single_turn_review_when_no_command_bus(
            self, mock_pr_repository, mock_changeset_fetcher,
            mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        """Test review flow when no command_bus is available (single-turn review)."""
        cmd = _cmd()
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        mock_llm_review.review_prompt.return_value = _review(
            ReviewVerdict.APPROVED
        )

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
            command_bus=None,  # No command bus → single-turn review
        ).execute(cmd)

        mock_changeset_fetcher.fetch.assert_called_once()
        mock_review_context_factory.build.assert_called_once()
        mock_llm_review.review_prompt.assert_called_once()
        mock_review_publisher.publish.assert_called_once()
        mock_pr_repository.save.assert_called_once()
        assert mock_pr_repository.save.call_args.args[0].head_sha == cmd.head_sha