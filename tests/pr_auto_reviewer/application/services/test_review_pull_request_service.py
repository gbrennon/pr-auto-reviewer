"""Application-layer tests for ReviewPullRequestService.

Uses injected test stubs (not MagicMock) that implement port Protocols.
All domain objects are real — PullRequest, CodeReview, PullRequestDiff.
Diff fixtures come from tests/fixtures/diffs/.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

from pr_auto_reviewer.application.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)
from pr_auto_reviewer.application.services import ReviewPullRequestService
from pr_auto_reviewer.domain import (
    CodeReview,
    CommitSha,
    EmptyDiffError,
    PullRequest,
    PullRequestDiff,
    PullRequestId,
    RepositoryContext,
    ReviewVerdict,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt

from tests.pr_auto_reviewer.application.stubs import (
    StubPullRequestRepository,
    StubChangesetFetcher,
    StubLlmReview,
    StubReviewPublisher,
    StubReviewContextFactory,
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
    def test_new_pr_full_flow(self):
        cmd = _cmd()
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        pr_repo = StubPullRequestRepository(initial=None)
        changeset = StubChangesetFetcher(diff)
        factory = StubReviewContextFactory()
        llm = StubLlmReview(_review(ReviewVerdict.APPROVED))
        publisher = StubReviewPublisher()

        ReviewPullRequestService(
            pr_repo,
            changeset,
            factory,
            llm,
            publisher,
        ).execute(cmd)

        assert pr_repo.find_calls == [cmd.pr_id]
        assert changeset.fetch_calls == [(cmd.pr_id, cmd.head_sha)]
        assert len(factory.build_calls) == 1
        assert len(llm.review_prompt_calls) == 1
        assert len(publisher.publish_calls) == 1
        assert len(pr_repo.save_calls) == 1
        assert pr_repo.save_calls[0].head_sha == cmd.head_sha

    def test_already_reviewed_sha_skips_review(self):
        cmd = _cmd()
        existing = _pr(cmd.pr_id, cmd.head_sha)
        existing = existing.add_review(_review(), cmd.head_sha)
        pr_repo = StubPullRequestRepository(initial=existing)
        changeset = StubChangesetFetcher(_diff_fixture(cmd.pr_id, cmd.head_sha))
        factory = StubReviewContextFactory()
        llm = StubLlmReview(_review())
        publisher = StubReviewPublisher()

        ReviewPullRequestService(
            pr_repo,
            changeset,
            factory,
            llm,
            publisher,
        ).execute(cmd)

        assert len(changeset.fetch_calls) == 0
        assert len(factory.build_calls) == 0
        assert len(llm.review_prompt_calls) == 0
        assert len(publisher.publish_calls) == 0
        assert len(pr_repo.save_calls) == 1

    def test_force_bypasses_idempotency_guard(self):
        sha = _sha()
        cmd = ReviewPullRequestCommand(
            pr_id=_pr_id(),
            head_sha=sha,
            title="Add feature X",
            force=True,
        )
        existing = _pr(cmd.pr_id, sha)
        existing = existing.add_review(_review(), sha)
        pr_repo = StubPullRequestRepository(initial=existing)
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        changeset = StubChangesetFetcher(diff)
        factory = StubReviewContextFactory()
        llm = StubLlmReview(_review(ReviewVerdict.APPROVED))
        publisher = StubReviewPublisher()

        ReviewPullRequestService(
            pr_repo,
            changeset,
            factory,
            llm,
            publisher,
        ).execute(cmd)

        assert len(changeset.fetch_calls) == 1
        assert len(factory.build_calls) == 1
        assert len(llm.review_prompt_calls) == 1
        assert len(publisher.publish_calls) == 1
        assert len(pr_repo.save_calls) == 1

    def test_empty_diff_raises(self):
        pr_repo = StubPullRequestRepository(initial=None)
        changeset = StubChangesetFetcher(
            PullRequestDiff(
                pr_id=_pr_id(),
                head_sha=_sha(),
                diff_content="   \n ",
            )
        )
        svc = ReviewPullRequestService(
            pr_repo,
            changeset,
            StubReviewContextFactory(),
            StubLlmReview(_review()),
            StubReviewPublisher(),
        )
        with pytest.raises(EmptyDiffError):
            svc.execute(_cmd())

    def test_existing_pr_new_sha_runs_full_flow(self):
        old, new = _sha("old111"), _sha("new222")
        cmd = _cmd(sha=new)
        existing = _pr(cmd.pr_id, old)
        existing = existing.add_review(_review(ReviewVerdict.COMMENTED), old)
        pr_repo = StubPullRequestRepository(initial=existing)
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        changeset = StubChangesetFetcher(diff)
        factory = StubReviewContextFactory()
        llm = StubLlmReview(_review(ReviewVerdict.APPROVED))
        publisher = StubReviewPublisher()

        ReviewPullRequestService(
            pr_repo,
            changeset,
            factory,
            llm,
            publisher,
        ).execute(cmd)

        assert len(changeset.fetch_calls) == 1
        assert len(factory.build_calls) == 1
        assert len(llm.review_prompt_calls) == 1
        assert len(publisher.publish_calls) == 1

    def test_debug_logs_review_complete_summary(self, caplog):
        cmd = _cmd()
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        pr_repo = StubPullRequestRepository(initial=None)
        changeset = StubChangesetFetcher(diff)
        factory = StubReviewContextFactory()
        llm = StubLlmReview(_review(ReviewVerdict.CHANGES_REQUESTED))
        publisher = StubReviewPublisher()

        caplog.set_level(logging.DEBUG)
        ReviewPullRequestService(
            pr_repo,
            changeset,
            factory,
            llm,
            publisher,
        ).execute(cmd)

        summaries = [
            r.message for r in caplog.records if "REVIEW COMPLETE" in r.message
        ]
        assert len(summaries) == 1
        assert "verdict=changes_requested" in summaries[0]
        assert "items=0" in summaries[0]
        assert "summary='Looks good'" in summaries[0]

    def test_review_complete_summary_not_logged_at_info(self, caplog):
        cmd = _cmd()
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        pr_repo = StubPullRequestRepository(initial=None)
        changeset = StubChangesetFetcher(diff)
        factory = StubReviewContextFactory()
        llm = StubLlmReview(_review())
        publisher = StubReviewPublisher()

        caplog.set_level(logging.INFO)
        ReviewPullRequestService(
            pr_repo,
            changeset,
            factory,
            llm,
            publisher,
        ).execute(cmd)

        summaries = [
            r.message for r in caplog.records if "REVIEW COMPLETE" in r.message
        ]
        assert len(summaries) == 0

    def test_review_complete_summary_not_logged_when_skipped(self, caplog):
        cmd = _cmd()
        existing = _pr(cmd.pr_id, cmd.head_sha)
        existing = existing.add_review(_review(), cmd.head_sha)
        pr_repo = StubPullRequestRepository(initial=existing)
        changeset = StubChangesetFetcher(_diff_fixture(cmd.pr_id, cmd.head_sha))
        factory = StubReviewContextFactory()
        llm = StubLlmReview(_review())
        publisher = StubReviewPublisher()

        caplog.set_level(logging.DEBUG)
        ReviewPullRequestService(
            pr_repo,
            changeset,
            factory,
            llm,
            publisher,
        ).execute(cmd)

        summaries = [
            r.message for r in caplog.records if "REVIEW COMPLETE" in r.message
        ]
        assert len(summaries) == 0

    def test_prompt_contains_diff_content(self):
        cmd = _cmd()
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        pr_repo = StubPullRequestRepository(initial=None)
        changeset = StubChangesetFetcher(diff)
        factory = StubReviewContextFactory()
        llm = StubLlmReview(_review())
        publisher = StubReviewPublisher()

        ReviewPullRequestService(
            pr_repo,
            changeset,
            factory,
            llm,
            publisher,
        ).execute(cmd)

        assert len(factory.build_calls) == 1
        assert len(llm.review_prompt_calls) == 1
        prompt = llm.review_prompt_calls[0]
        assert isinstance(prompt, ComposedPrompt)
        assert len(prompt.content) > 50
        assert "diff --git" in prompt.content

    def test_prompt_contains_reviewer_instructions(self):
        cmd = _cmd()
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        pr_repo = StubPullRequestRepository(initial=None)
        changeset = StubChangesetFetcher(diff)
        factory = StubReviewContextFactory()
        llm = StubLlmReview(_review())
        publisher = StubReviewPublisher()

        ReviewPullRequestService(
            pr_repo,
            changeset,
            factory,
            llm,
            publisher,
        ).execute(cmd)

        prompt = llm.review_prompt_calls[0]
        assert "Senior Principal Software Engineer" in prompt.content
        assert "Code Reviewer" in prompt.content
        assert "report issues as JSON" in prompt.content

    def test_prompt_is_not_empty_json_template(self):
        cmd = _cmd()
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        pr_repo = StubPullRequestRepository(initial=None)
        changeset = StubChangesetFetcher(diff)
        factory = StubReviewContextFactory()
        llm = StubLlmReview(_review())
        publisher = StubReviewPublisher()

        ReviewPullRequestService(
            pr_repo,
            changeset,
            factory,
            llm,
            publisher,
        ).execute(cmd)

        prompt = llm.review_prompt_calls[0]
        assert len(prompt.content) > 200
        assert prompt.content.strip() != ""
        assert prompt.total_tokens > 10

    def test_prompt_includes_pr_title_when_present(self):
        cmd = ReviewPullRequestCommand(
            pr_id=_pr_id(),
            head_sha=_sha(),
            title="Fix SQL injection in login handler",
        )
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        pr_repo = StubPullRequestRepository(initial=None)
        changeset = StubChangesetFetcher(diff)
        factory = StubReviewContextFactory()
        llm = StubLlmReview(_review())
        publisher = StubReviewPublisher()

        ReviewPullRequestService(
            pr_repo,
            changeset,
            factory,
            llm,
            publisher,
        ).execute(cmd)

        prompt = llm.review_prompt_calls[0]
        assert "Fix SQL injection in login handler" in prompt.content

    def test_factory_receives_diff_in_build_call(self):
        cmd = _cmd()
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        pr_repo = StubPullRequestRepository(initial=None)
        changeset = StubChangesetFetcher(diff)
        factory = StubReviewContextFactory()
        llm = StubLlmReview(_review())
        publisher = StubReviewPublisher()

        ReviewPullRequestService(
            pr_repo,
            changeset,
            factory,
            llm,
            publisher,
        ).execute(cmd)

        assert len(factory.build_calls) == 1
        _pr_id_arg, build_diff, _title, _desc = factory.build_calls[0]
        assert build_diff is diff
        assert "diff --git" in build_diff.diff_content

    def test_adds_concrete_finding_for_noisy_info_log_when_llm_misses_it(self):
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
        pr_repo = StubPullRequestRepository(initial=None)
        changeset = StubChangesetFetcher(diff)
        factory = StubReviewContextFactory()
        llm = StubLlmReview(_review(ReviewVerdict.APPROVED))
        publisher = StubReviewPublisher()

        ReviewPullRequestService(
            pr_repo,
            changeset,
            factory,
            llm,
            publisher,
        ).execute(cmd)

        _pr_id_arg, review = publisher.publish_calls[0]
        assert len(review.items) == 1
        assert review.items[0].file_path == "src/client.py"
        assert review.items[0].current_code == (
            '        logger.info("GET %s params=%s", url, params)'
        )
        assert review.items[0].suggested_fix == (
            '        logger.debug("GET %s params=%s", url, params)'
        )

    def test_adds_noisy_log_findings_before_llm_findings(self):
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
                ReviewItem(
                    number=1,
                    severity="minor",
                    category="quality",
                    file_path="src/other.py",
                    description="existing",
                    current_code="x = 1",
                    suggested_fix="x = 2",
                )
            ],
        )
        publisher = StubReviewPublisher()

        ReviewPullRequestService(
            StubPullRequestRepository(initial=None),
            StubChangesetFetcher(diff),
            StubReviewContextFactory(),
            StubLlmReview(llm_review),
            publisher,
        ).execute(cmd)

        _pr_id_arg, review = publisher.publish_calls[0]
        assert len(review.items) == 2
        assert review.items[0].file_path == "src/client.py"
        assert review.items[1].file_path == "src/other.py"

    def test_skips_log_info_without_noisy_marker(self):
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
        pr_repo = StubPullRequestRepository(initial=None)
        changeset = StubChangesetFetcher(diff)
        llm = StubLlmReview(_review(ReviewVerdict.APPROVED))
        publisher = StubReviewPublisher()

        ReviewPullRequestService(
            pr_repo,
            changeset,
            StubReviewContextFactory(),
            llm,
            publisher,
        ).execute(cmd)

        _pr_id_arg, review = publisher.publish_calls[0]
        assert len(review.items) == 0

    def test_limits_noisy_log_findings_to_five(self):
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
        pr_repo = StubPullRequestRepository(initial=None)
        changeset = StubChangesetFetcher(diff)
        llm = StubLlmReview(_review(ReviewVerdict.APPROVED))
        publisher = StubReviewPublisher()

        ReviewPullRequestService(
            pr_repo,
            changeset,
            StubReviewContextFactory(),
            llm,
            publisher,
        ).execute(cmd)

        _pr_id_arg, review = publisher.publish_calls[0]
        assert len(review.items) == 5
