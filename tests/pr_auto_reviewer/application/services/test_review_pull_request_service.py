"""Application-layer tests for ReviewPullRequestService.

Uses injected test stubs (not MagicMock) that implement port Protocols.
All domain objects are real — PullRequest, CodeReview, PullRequestDiff.
Diff fixtures come from tests/fixtures/diffs/.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pr_auto_reviewer.application.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)
from pr_auto_reviewer.application.services import ReviewPullRequestService
from pr_auto_reviewer.domain import (
    CodeReview, CommitSha, EmptyDiffError, PullRequest, PullRequestDiff,
    PullRequestId, RepositoryContext, ReviewVerdict,
)

from tests.pr_auto_reviewer.application.stubs import (
    StubPullRequestRepository,
    StubChangesetFetcher,
    StubRepositoryContext,
    StubLlmReview,
    StubReviewPublisher,
)

FIXTURES = Path(__file__).resolve().parents[3] / "fixtures" / "diffs"


def _pr_id(repo="owner/repo", num=42):
    return PullRequestId(repository=repo, number=num)

def _sha(v="abc123"):
    return CommitSha(value=v)

def _cmd(pr_id=None, sha=None):
    return ReviewPullRequestCommand(
        pr_id=pr_id or _pr_id(), head_sha=sha or _sha(), title="Add feature X",
    )

def _diff_fixture(pr_id, sha):
    return PullRequestDiff(
        pr_id=pr_id, head_sha=sha,
        diff_content=(FIXTURES / "sample-service.diff").read_text(),
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
        repo_ctx = StubRepositoryContext(RepositoryContext(architecture_hint="hint"))
        llm = StubLlmReview(_review(ReviewVerdict.APPROVED))
        publisher = StubReviewPublisher()

        ReviewPullRequestService(
            pr_repo, changeset, repo_ctx, llm, publisher,
        ).execute(cmd)

        assert pr_repo.find_calls == [cmd.pr_id]
        assert changeset.fetch_calls == [(cmd.pr_id, cmd.head_sha)]
        assert len(llm.review_calls) == 1
        assert len(publisher.publish_calls) == 1
        assert len(pr_repo.save_calls) == 1
        assert pr_repo.save_calls[0].head_sha == cmd.head_sha

    def test_already_reviewed_sha_skips_review(self):
        cmd = _cmd()
        existing = _pr(cmd.pr_id, cmd.head_sha)
        existing = existing.add_review(_review(), cmd.head_sha)
        pr_repo = StubPullRequestRepository(initial=existing)
        changeset = StubChangesetFetcher(_diff_fixture(cmd.pr_id, cmd.head_sha))
        llm = StubLlmReview(_review())
        publisher = StubReviewPublisher()

        ReviewPullRequestService(
            pr_repo, changeset, StubRepositoryContext(), llm, publisher,
        ).execute(cmd)

        assert len(changeset.fetch_calls) == 0
        assert len(llm.review_calls) == 0
        assert len(publisher.publish_calls) == 0
        assert len(pr_repo.save_calls) == 1

    def test_force_bypasses_idempotency_guard(self):
        sha = _sha()
        cmd = ReviewPullRequestCommand(
            pr_id=_pr_id(), head_sha=sha, title="Add feature X", force=True,
        )
        existing = _pr(cmd.pr_id, sha)
        existing = existing.add_review(_review(), sha)
        pr_repo = StubPullRequestRepository(initial=existing)
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        changeset = StubChangesetFetcher(diff)
        repo_ctx = StubRepositoryContext(RepositoryContext(architecture_hint="hint"))
        llm = StubLlmReview(_review(ReviewVerdict.APPROVED))
        publisher = StubReviewPublisher()

        ReviewPullRequestService(
            pr_repo, changeset, repo_ctx, llm, publisher,
        ).execute(cmd)

        assert len(changeset.fetch_calls) == 1
        assert len(llm.review_calls) == 1
        assert len(publisher.publish_calls) == 1
        assert len(pr_repo.save_calls) == 1

    def test_empty_diff_raises(self):
        pr_repo = StubPullRequestRepository(initial=None)
        changeset = StubChangesetFetcher(PullRequestDiff(
            pr_id=_pr_id(), head_sha=_sha(), diff_content="   \n ",
        ))
        svc = ReviewPullRequestService(
            pr_repo, changeset, StubRepositoryContext(),
            StubLlmReview(_review()), StubReviewPublisher(),
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
        repo_ctx = StubRepositoryContext(RepositoryContext(architecture_hint="hint"))
        llm = StubLlmReview(_review(ReviewVerdict.APPROVED))
        publisher = StubReviewPublisher()

        ReviewPullRequestService(
            pr_repo, changeset, repo_ctx, llm, publisher,
        ).execute(cmd)

        assert len(changeset.fetch_calls) == 1
        assert len(llm.review_calls) == 1
        assert len(publisher.publish_calls) == 1
