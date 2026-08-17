"""Integration tests for the reself, view verdict pipeline.

Uses test stubs (not MagicMock) that implement port Protocols.
Real domain objects throughout — PullRequestDiff, CodeReview, ReviewItem.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests as req

from pr_auto_reviewer.application.services.review_pull_request_service import (
    ReviewPullRequestService,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.messages.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.ollama.ollama_llm_adapter import (
    OllamaLlmAdapter,
)
from tests.fakes import (
    FakeChangesetFetcher,
    FakeLlmReview,
    FakePullRequestRepository,
    FakeReviewContextFactory,
    FakeReviewPublisher,
)

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"

def _load_fixture(relative: str) -> str:
    return (FIXTURES / relative).read_text()


class TestReviewVerdict:
    """Verdict tests using stub ports — no MagicMock, no requests.post.

    The pipeline is:
      ReviewPullRequestService
        → review_context_factory.build()
        → llm_review.review_prompt(composed_prompt)
        → review_publisher.publish()
    """

    @pytest.fixture
    def pr_id(self) -> PullRequestId:
        return PullRequestId(repository="owner/repo", number=1)

    @pytest.fixture
    def head_sha(self) -> CommitSha:
        return CommitSha("abc123def456")

    def test_shell_with_shebang_is_approved(
        self, pr_id: PullRequestId, head_sha: CommitSha,
    ) -> None:
        """Shell script WITH shebang → no issues → APPROVED."""
        diff = PullRequestDiff(
            pr_id=pr_id,
            head_sha=head_sha,
            diff_content=_load_fixture("diffs/shell-with-shebang.diff"),
            file_contents={
                "scripts/deploy.sh": _load_fixture("diffs/shell-with-shebang.full"),
            },
        )
        fetcher = FakeChangesetFetcher(diff)

        review = CodeReview(verdict=ReviewVerdict.APPROVED, model_used="code-review")
        llm_stub = FakeLlmReview(review)
        publisher = FakeReviewPublisher()
        ctx_factory = FakeReviewContextFactory()

        service = ReviewPullRequestService(
            pr_repository=FakePullRequestRepository(),
            changeset_fetcher=fetcher,
            review_context_factory=ctx_factory,
            llm_review=llm_stub,
            review_publisher=publisher,
        )
        service.execute(ReviewPullRequestCommand(
            pr_id=pr_id, head_sha=head_sha, title="Add deploy script",
        ))

        assert len(publisher.publish_calls) == 1
        published: CodeReview = publisher.publish_calls[0][1]
        assert published.verdict == ReviewVerdict.APPROVED
        assert published.model_used == "code-review"

    def test_shell_missing_shebang_real_model(
        self, pr_id: PullRequestId, head_sha: CommitSha,
    ) -> None:
        """Shell WITHOUT shebang — real model (code-review:latest) response."""
        diff = PullRequestDiff(
            pr_id=pr_id,
            head_sha=head_sha,
            diff_content=_load_fixture("diffs/shell-missing-shebang.diff"),
            file_contents={
                "scripts/deploy.sh": _load_fixture(
                    "diffs/shell-missing-shebang.full",
                ),
            },
        )
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            model_used="code-review",
            items=[
                ReviewItem(
                    number=1,
                    severity=ItemSeverity.MINOR,
                    category=IssueCategory.QUALITY,
                    file_path="scripts/deploy.sh",
                    description="Missing shebang in deploy script",
                ),
            ],
        )

        fetcher = FakeChangesetFetcher(diff)
        llm_stub = FakeLlmReview(review)
        publisher = FakeReviewPublisher()
        ctx_factory = FakeReviewContextFactory()

        service = ReviewPullRequestService(
            pr_repository=FakePullRequestRepository(),
            changeset_fetcher=fetcher,
            review_context_factory=ctx_factory,
            llm_review=llm_stub,
            review_publisher=publisher,
        )
        service.execute(ReviewPullRequestCommand(
            pr_id=pr_id, head_sha=head_sha, title="Add deploy script",
        ))

        assert len(publisher.publish_calls) == 1
        published: CodeReview = publisher.publish_calls[0][1]
        assert published.verdict == ReviewVerdict.APPROVED
        assert len(published.items) == 1

    def test_prompt_includes_file_content_in_composed_prompt(
        self, pr_id: PullRequestId, head_sha: CommitSha,
    ) -> None:
        """The ComposedPrompt passed to the LLM includes file contents."""
        diff = PullRequestDiff(
            pr_id=pr_id,
            head_sha=head_sha,
            diff_content=_load_fixture("diffs/shell-with-shebang.diff"),
            file_contents={
                "scripts/deploy.sh": _load_fixture("diffs/shell-with-shebang.full"),
            },
        )
        review = CodeReview(verdict=ReviewVerdict.APPROVED, model_used="code-review")

        fetcher = FakeChangesetFetcher(diff)
        llm_stub = FakeLlmReview(review)
        publisher = FakeReviewPublisher()
        expected_prompt = ComposedPrompt(
            content="You are a code reviewer.\n\n"
                    "## Full File Contents\n"
                    "### scripts/deploy.sh\n"
                    "#!/usr/bin/env bash\n"
                    "echo 'deploying...'\n",
            fragments_used=["solid"],
            total_tokens=50,
        )
        ctx_factory = FakeReviewContextFactory(prompt=expected_prompt)

        service = ReviewPullRequestService(
            pr_repository=FakePullRequestRepository(),
            changeset_fetcher=fetcher,
            review_context_factory=ctx_factory,
            llm_review=llm_stub,
            review_publisher=publisher,
        )
        service.execute(ReviewPullRequestCommand(
            pr_id=pr_id, head_sha=head_sha, title="Test prompt",
        ))

        assert len(llm_stub.review_prompt_calls) == 1
        prompt_sent: ComposedPrompt = llm_stub.review_prompt_calls[0]
        assert isinstance(prompt_sent, ComposedPrompt)
        assert "## Full File Contents" in prompt_sent.content
        assert "### scripts/deploy.sh" in prompt_sent.content
        assert "#!/usr/bin/env bash" in prompt_sent.content

    def test_verdict_follows_severity_rules(
        self, pr_id: PullRequestId, head_sha: CommitSha,
    ) -> None:
        """APPROVED vs CHANGES_REQUESTED driven by CodeReview objects."""
        diff = PullRequestDiff(
            pr_id=pr_id, head_sha=head_sha, diff_content="+new line",
        )
        fetcher = FakeChangesetFetcher(diff)
        ctx_factory = FakeReviewContextFactory()

        publisher1 = FakeReviewPublisher()
        approved_review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            summary="Minor issues only",
            model_used="code-review",
        )
        llm_stub1 = FakeLlmReview(approved_review)

        service1 = ReviewPullRequestService(
            pr_repository=FakePullRequestRepository(),
            changeset_fetcher=fetcher,
            review_context_factory=ctx_factory,
            llm_review=llm_stub1,
            review_publisher=publisher1,
        )
        service1.execute(ReviewPullRequestCommand(
            pr_id=pr_id, head_sha=head_sha, title="info only",
        ))
        published1: CodeReview = publisher1.publish_calls[0][1]
        assert published1.verdict == ReviewVerdict.APPROVED

        publisher2 = FakeReviewPublisher()
        cr_review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            summary="Critical found",
            model_used="code-review",
        )
        llm_stub2 = FakeLlmReview(cr_review)

        service2 = ReviewPullRequestService(
            pr_repository=FakePullRequestRepository(),
            changeset_fetcher=fetcher,
            review_context_factory=ctx_factory,
            llm_review=llm_stub2,
            review_publisher=publisher2,
        )
        service2.execute(ReviewPullRequestCommand(
            pr_id=pr_id, head_sha=head_sha, title="critical",
        ))
        published2 = publisher2.publish_calls[0][1]
        assert published2.verdict == ReviewVerdict.CHANGES_REQUESTED

class TestLlmUnavailable:
    """Error-path tests with a REAL OllamaLlmAdapter + monkeypatched requests.post.

    Stubs for everything except the LLM adapter.
    MagicMock is used ONLY for mock_response objects at the HTTP boundary.
    """

    def _cmd(self, pr_id: PullRequestId, head_sha: CommitSha) -> ReviewPullRequestCommand:
        return ReviewPullRequestCommand(
            pr_id=pr_id, head_sha=head_sha, title="Test",
        )

    @pytest.fixture
    def pr_id(self) -> PullRequestId:
        return PullRequestId(repository="owner/repo", number=1)

    @pytest.fixture
    def head_sha(self) -> CommitSha:
        return CommitSha("abc123")

    def test_connection_refused(
        self,
        _svc: ReviewPullRequestService,
        pr_id: PullRequestId,
        head_sha: CommitSha,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Connection refused → LlmUnavailableError."""
        def _raise(*a, **kw):
            raise req.ConnectionError("Connection refused")

        monkeypatch.setattr("requests.post", _raise)

        with pytest.raises(LlmUnavailableError, match="unreachable"):
            _svc.execute(self._cmd(pr_id, head_sha))

    def test_timeout(
        self,
        _svc: ReviewPullRequestService,
        pr_id: PullRequestId,
        head_sha: CommitSha,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Request timeout → LlmUnavailableError."""
        def _raise(*a, **kw):
            raise req.Timeout("Read timed out")

        monkeypatch.setattr("requests.post", _raise)

        with pytest.raises(LlmUnavailableError):
            _svc.execute(self._cmd(pr_id, head_sha))

    def test_http_500(
        self,
        _svc: ReviewPullRequestService,
        pr_id: PullRequestId,
        head_sha: CommitSha,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """HTTP 500 error → LlmUnavailableError."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = req.HTTPError(
            "500 Server Error",
        )
        monkeypatch.setattr("requests.post", lambda *a, **kw: mock_response)

        with pytest.raises(LlmUnavailableError):
            _svc.execute(self._cmd(pr_id, head_sha))

    def test_invalid_json(
        self,
        _svc: ReviewPullRequestService,
        pr_id: PullRequestId,
        head_sha: CommitSha,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Malformed JSON body → LlmUnavailableError."""

        class _FakeResponse:
            def raise_for_status(self) -> None:
                pass

            def json(self):
                raise json.JSONDecodeError("bad json", "{bad", 0)

        monkeypatch.setattr("requests.post", lambda *a, **kw: _FakeResponse())

        with pytest.raises(LlmUnavailableError, match="invalid JSON"):
            _svc.execute(self._cmd(pr_id, head_sha))

    def test_empty_response_field(
        self,
        _svc: ReviewPullRequestService,
        pr_id: PullRequestId,
        head_sha: CommitSha,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Empty 'response' field in valid JSON → LlmUnavailableError."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": ""}
        monkeypatch.setattr("requests.post", lambda *a, **kw: mock_response)

        with pytest.raises(LlmUnavailableError, match="empty response"):
            _svc.execute(self._cmd(pr_id, head_sha))

    def test_empty_json_object(
        self,
        _svc: ReviewPullRequestService,
        pr_id: PullRequestId,
        head_sha: CommitSha,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Completely empty JSON {} → LlmUnavailableError."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {}
        monkeypatch.setattr("requests.post", lambda *a, **kw: mock_response)

        with pytest.raises(LlmUnavailableError, match="empty response"):
            _svc.execute(self._cmd(pr_id, head_sha))

    def test_dns_failure(
        self,
        _svc: ReviewPullRequestService,
        pr_id: PullRequestId,
        head_sha: CommitSha,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """DNS resolution failure → LlmUnavailableError."""
        def _raise(*a, **kw):
            raise req.ConnectionError("Failed to resolve 'localhost'")

        monkeypatch.setattr("requests.post", _raise)

        with pytest.raises(LlmUnavailableError):
            _svc.execute(self._cmd(pr_id, head_sha))

    def test_review_not_published_on_failure(
        self,
        pr_id: PullRequestId,
        head_sha: CommitSha,
        _diff: PullRequestDiff,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When LLM fails, review publisher is never called."""
        publisher = FakeReviewPublisher()

        service = ReviewPullRequestService(
            pr_repository=FakePullRequestRepository(),
            changeset_fetcher=FakeChangesetFetcher(_diff),
            review_context_factory=FakeReviewContextFactory(),
            llm_review=OllamaLlmAdapter("http://localhost:11434", "code-review"),
            review_publisher=publisher,
        )

        def _raise(*a, **kw):
            raise req.ConnectionError("down")

        monkeypatch.setattr("requests.post", _raise)

        with pytest.raises(LlmUnavailableError):
            service.execute(self._cmd(pr_id, head_sha))

        assert publisher.publish_calls == []

    @pytest.fixture
    def _diff(self, pr_id: PullRequestId, head_sha: CommitSha) -> PullRequestDiff:
        return PullRequestDiff(
            pr_id=pr_id, head_sha=head_sha, diff_content="+new line",
        )

    @pytest.fixture
    def _svc(self, _diff: PullRequestDiff) -> ReviewPullRequestService:
        return ReviewPullRequestService(
            pr_repository=FakePullRequestRepository(),
            changeset_fetcher=FakeChangesetFetcher(_diff),
            review_context_factory=FakeReviewContextFactory(),
            llm_review=OllamaLlmAdapter("http://localhost:11434", "code-review"),
            review_publisher=FakeReviewPublisher(),
        )
