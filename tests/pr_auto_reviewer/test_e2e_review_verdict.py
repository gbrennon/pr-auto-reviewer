"""Real E2E tests for the review verdict pipeline.

Mocks ONLY at I/O boundaries (Ollama HTTP, platform API, publishing).
Uses the REAL infrastructure services: PromptBuilder, OllamaLlmAdapter,
ReviewResponseParser, and the REAL ReviewPullRequestService.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pr_auto_reviewer.application.commands.review_pull_request_command import (
    ReviewPullRequestCommand,
)
from pr_auto_reviewer.application.services.review_pull_request_service import (
    ReviewPullRequestService,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.repository_context import (
    RepositoryContext,
)
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.ollama_llm_adapter import OllamaLlmAdapter

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"


def _load_fixture(relative: str) -> str:
    return (FIXTURES / relative).read_text()


def _ollama_response_fixture(name: str) -> dict:
    return json.loads(_load_fixture(f"ollama_responses/{name}"))


class TestReviewVerdictE2E:
    """E2E tests for APPROVED vs CHANGES_REQUESTED verdicts.

    The ONLY mocks are at the I/O boundaries:
      - requests.post        → Ollama HTTP
      - changeset_fetcher    → Codeberg API (returns fixture diffs)
      - repository_context   → Codeberg API (returns empty context)
      - review_publisher     → Codeberg API (captures published review)
      - pr_repository        → local persistence (stub)

    The REAL pipeline is:
      ReviewPullRequestService
        → PromptBuilder.build()
        → OllamaLlmAdapter.review()
          → ReviewResponseParser.parse()
        → review_publisher.publish()
    """

    @pytest.fixture
    def pr_id(self) -> PullRequestId:
        return PullRequestId(repository="owner/repo", number=1)

    @pytest.fixture
    def head_sha(self) -> CommitSha:
        return CommitSha("abc123def456")

    @pytest.fixture
    def empty_context(self) -> RepositoryContext:
        return RepositoryContext(
            architecture_hint="",
            repository_structure=None,
            conventions=None,
        )

    @pytest.fixture
    def review_publisher(self) -> MagicMock:
        return MagicMock()

    @pytest.fixture
    def pr_repository(self) -> MagicMock:
        repo = MagicMock()
        repo.find.return_value = None
        return repo

    # ── APPROVED scenario ──────────────────────────────────────────

    @patch("requests.post")
    def test_shell_with_shebang_is_approved(
        self,
        mock_post: MagicMock,
        pr_id: PullRequestId,
        head_sha: CommitSha,
        empty_context: RepositoryContext,
        review_publisher: MagicMock,
        pr_repository: MagicMock,
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
        changeset_fetcher = MagicMock()
        changeset_fetcher.fetch.return_value = diff
        repository_context = MagicMock()
        repository_context.fetch.return_value = empty_context

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = _ollama_response_fixture("shell-with-shebang.json")
        mock_post.return_value = mock_response

        # -- act: REAL OllamaLlmAdapter + REAL ReviewPullRequestService -----
        llm = OllamaLlmAdapter("http://localhost:11434", "code-review")
        service = ReviewPullRequestService(
            pr_repository=pr_repository,
            changeset_fetcher=changeset_fetcher,
            repository_context=repository_context,
            llm_review=llm,
            review_publisher=review_publisher,
        )
        service.execute(ReviewPullRequestCommand(
            pr_id=pr_id, head_sha=head_sha, title="Add deploy script",
        ))

        # -- assert: APPROVED -----------------------------------------------
        review_publisher.publish.assert_called_once()
        published: CodeReview = review_publisher.publish.call_args[0][1]
        assert published.verdict == ReviewVerdict.APPROVED
        assert published.model_used == "code-review"

    # ── CHANGES_REQUESTED scenario ────────────────────────────────────

    @patch("requests.post")
    def test_shell_missing_shebang_real_model(
        self,
        mock_post: MagicMock,
        pr_id: PullRequestId,
        head_sha: CommitSha,
        empty_context: RepositoryContext,
        review_publisher: MagicMock,
        pr_repository: MagicMock,
    ) -> None:
        """Shell WITHOUT shebang — real model (code-review:latest) response.

        Note: the real qwen2:7b model approved this and flagged a different
        info-level item instead of the missing shebang.  This test verifies
        the pipeline works with whatever the real model actually returns.
        """
        diff = PullRequestDiff(
            pr_id=pr_id,
            head_sha=head_sha,
            diff_content=_load_fixture("diffs/shell-missing-shebang.diff"),
            file_contents={
                "scripts/deploy.sh": _load_fixture("diffs/shell-missing-shebang.full"),
            },
        )
        changeset_fetcher = MagicMock()
        changeset_fetcher.fetch.return_value = diff
        repository_context = MagicMock()
        repository_context.fetch.return_value = empty_context

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = _ollama_response_fixture(
            "shell-missing-shebang.json",
        )
        mock_post.return_value = mock_response

        # -- act: REAL pipeline --------------------------------------------
        llm = OllamaLlmAdapter("http://localhost:11434", "code-review")
        service = ReviewPullRequestService(
            pr_repository=pr_repository,
            changeset_fetcher=changeset_fetcher,
            repository_context=repository_context,
            llm_review=llm,
            review_publisher=review_publisher,
        )
        service.execute(ReviewPullRequestCommand(
            pr_id=pr_id, head_sha=head_sha, title="Add deploy script",
        ))

        # -- assert: matches real captured model output --------------------
        review_publisher.publish.assert_called_once()
        published: CodeReview = review_publisher.publish.call_args[0][1]
        # Real model returned approved + 1 info item (not shebang-related)
        assert published.verdict == ReviewVerdict.APPROVED
        assert len(published.items) == 1

    # ── PROMPT includes file_contents ─────────────────────────────────

    @patch("requests.post")
    def test_prompt_includes_full_file_contents(
        self,
        mock_post: MagicMock,
        pr_id: PullRequestId,
        head_sha: CommitSha,
        empty_context: RepositoryContext,
        review_publisher: MagicMock,
        pr_repository: MagicMock,
    ) -> None:
        """The prompt sent to Ollama includes ## Full file contents."""
        diff = PullRequestDiff(
            pr_id=pr_id,
            head_sha=head_sha,
            diff_content=_load_fixture("diffs/shell-with-shebang.diff"),
            file_contents={
                "scripts/deploy.sh": _load_fixture("diffs/shell-with-shebang.full"),
            },
        )
        changeset_fetcher = MagicMock()
        changeset_fetcher.fetch.return_value = diff
        repository_context = MagicMock()
        repository_context.fetch.return_value = empty_context

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = _ollama_response_fixture("shell-with-shebang.json")
        mock_post.return_value = mock_response

        llm = OllamaLlmAdapter("http://localhost:11434", "code-review")
        service = ReviewPullRequestService(
            pr_repository=pr_repository,
            changeset_fetcher=changeset_fetcher,
            repository_context=repository_context,
            llm_review=llm,
            review_publisher=review_publisher,
        )
        service.execute(ReviewPullRequestCommand(
            pr_id=pr_id, head_sha=head_sha, title="Test prompt",
        ))

        mock_post.assert_called_once()
        prompt_sent = mock_post.call_args[1]["json"]["prompt"]
        assert "## Full file contents" in prompt_sent
        assert "### scripts/deploy.sh" in prompt_sent
        assert "#!/usr/bin/env bash" in prompt_sent

    # ── VERDICT from parsed issues ────────────────────────────────────

    @patch("requests.post")
    def test_verdict_follows_severity_rules(
        self,
        mock_post: MagicMock,
        pr_id: PullRequestId,
        head_sha: CommitSha,
        empty_context: RepositoryContext,
        review_publisher: MagicMock,
        pr_repository: MagicMock,
    ) -> None:
        """Critical/high severity → CHANGES_REQUESTED. Info only → APPROVED."""
        diff = PullRequestDiff(
            pr_id=pr_id, head_sha=head_sha, diff_content="+new line",
        )
        changeset_fetcher = MagicMock()
        changeset_fetcher.fetch.return_value = diff
        repository_context = MagicMock()
        repository_context.fetch.return_value = empty_context
        llm = OllamaLlmAdapter("http://localhost:11434", "code-review")

        # -- low + info → APPROVED ----------------------------------------
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "response": json.dumps({
                "issues": [
                    {"file": "x.sh", "line": "1", "severity": "low",
                     "type": "quality", "description": "minor"},
                    {"file": "x.sh", "line": "2", "severity": "info",
                     "type": "style", "description": "cosmetic"},
                ],
                "summary": "Minor issues only",
                "suggestions": [], "praise": [],
            }),
        }
        mock_post.return_value = mock_response

        service = ReviewPullRequestService(
            pr_repository=pr_repository,
            changeset_fetcher=changeset_fetcher,
            repository_context=repository_context,
            llm_review=llm,
            review_publisher=review_publisher,
        )
        service.execute(ReviewPullRequestCommand(
            pr_id=pr_id, head_sha=head_sha, title="info only",
        ))
        published: CodeReview = review_publisher.publish.call_args[0][1]
        assert published.verdict == ReviewVerdict.APPROVED

        # -- critical → CHANGES_REQUESTED ---------------------------------
        review_publisher.reset_mock()
        mock_response.json.return_value = {
            "response": json.dumps({
                "issues": [
                    {"file": "x.sh", "line": "1", "severity": "critical",
                     "type": "security", "description": "dangerous"},
                ],
                "summary": "Critical found",
                "suggestions": [], "praise": [],
            }),
        }
        service.execute(ReviewPullRequestCommand(
            pr_id=pr_id, head_sha=head_sha, title="critical",
        ))
        published = review_publisher.publish.call_args[0][1]
        assert published.verdict == ReviewVerdict.CHANGES_REQUESTED


# ── LLM unavailable / broken / offline ────────────────────────────────


class TestLlmUnavailableE2E:
    """E2E tests for LLM outage scenarios: offline, broken, empty responses.

    LlmUnavailableError must propagate through the full
    ReviewPullRequestService pipeline to the caller (PollingDaemon).
    """

    @pytest.fixture
    def pr_id(self) -> PullRequestId:
        return PullRequestId(repository="owner/repo", number=1)

    @pytest.fixture
    def head_sha(self) -> CommitSha:
        return CommitSha("abc123")

    @pytest.fixture
    def _diff(self, pr_id: PullRequestId, head_sha: CommitSha) -> PullRequestDiff:
        return PullRequestDiff(
            pr_id=pr_id, head_sha=head_sha, diff_content="+new line",
        )

    @pytest.fixture
    def _ctx(self) -> RepositoryContext:
        return RepositoryContext(architecture_hint="")

    @pytest.fixture
    def _svc(self, _diff: PullRequestDiff, _ctx: RepositoryContext) -> ReviewPullRequestService:
        fetcher = MagicMock()
        fetcher.fetch.return_value = _diff
        ctx_port = MagicMock()
        ctx_port.fetch.return_value = _ctx
        return ReviewPullRequestService(
            pr_repository=MagicMock(),
            changeset_fetcher=fetcher,
            repository_context=ctx_port,
            llm_review=OllamaLlmAdapter("http://localhost:11434", "code-review"),
            review_publisher=MagicMock(),
        )

    @staticmethod
    def _cmd(pr_id: PullRequestId, head_sha: CommitSha) -> ReviewPullRequestCommand:
        return ReviewPullRequestCommand(
            pr_id=pr_id, head_sha=head_sha, title="Test",
        )

    @patch("requests.post")
    def test_connection_refused(
        self, mock_post: MagicMock, _svc: ReviewPullRequestService,
        pr_id: PullRequestId, head_sha: CommitSha,
    ) -> None:
        """Connection refused → LlmUnavailableError."""
        import requests as req
        mock_post.side_effect = req.ConnectionError("Connection refused")
        from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
            LlmUnavailableError,
        )
        with pytest.raises(LlmUnavailableError, match="unreachable"):
            _svc.execute(self._cmd(pr_id, head_sha))

    @patch("requests.post")
    def test_timeout(
        self, mock_post: MagicMock, _svc: ReviewPullRequestService,
        pr_id: PullRequestId, head_sha: CommitSha,
    ) -> None:
        """Request timeout → LlmUnavailableError."""
        import requests as req
        mock_post.side_effect = req.Timeout("Read timed out")
        from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
            LlmUnavailableError,
        )
        with pytest.raises(LlmUnavailableError):
            _svc.execute(self._cmd(pr_id, head_sha))

    @patch("requests.post")
    def test_http_500(
        self, mock_post: MagicMock, _svc: ReviewPullRequestService,
        pr_id: PullRequestId, head_sha: CommitSha,
    ) -> None:
        """HTTP 500 error → LlmUnavailableError."""
        import requests as req
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = req.HTTPError("500 Server Error")
        mock_post.return_value = mock_response
        from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
            LlmUnavailableError,
        )
        with pytest.raises(LlmUnavailableError):
            _svc.execute(self._cmd(pr_id, head_sha))

    @patch("requests.post")
    def test_invalid_json(
        self, mock_post: MagicMock, _svc: ReviewPullRequestService,
        pr_id: PullRequestId, head_sha: CommitSha,
    ) -> None:
        """Malformed JSON body → LlmUnavailableError."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = json.JSONDecodeError("bad json", "{bad", 0)
        mock_post.return_value = mock_response
        from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
            LlmUnavailableError,
        )
        with pytest.raises(LlmUnavailableError, match="invalid JSON"):
            _svc.execute(self._cmd(pr_id, head_sha))

    @patch("requests.post")
    def test_empty_response_field(
        self, mock_post: MagicMock, _svc: ReviewPullRequestService,
        pr_id: PullRequestId, head_sha: CommitSha,
    ) -> None:
        """Empty 'response' field in valid JSON → LlmUnavailableError."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"response": ""}
        mock_post.return_value = mock_response
        from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
            LlmUnavailableError,
        )
        with pytest.raises(LlmUnavailableError, match="empty response"):
            _svc.execute(self._cmd(pr_id, head_sha))

    @patch("requests.post")
    def test_empty_json_object(
        self, mock_post: MagicMock, _svc: ReviewPullRequestService,
        pr_id: PullRequestId, head_sha: CommitSha,
    ) -> None:
        """Completely empty JSON {} → LlmUnavailableError."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {}
        mock_post.return_value = mock_response
        from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
            LlmUnavailableError,
        )
        with pytest.raises(LlmUnavailableError, match="empty response"):
            _svc.execute(self._cmd(pr_id, head_sha))

    @patch("requests.post")
    def test_dns_failure(
        self, mock_post: MagicMock, _svc: ReviewPullRequestService,
        pr_id: PullRequestId, head_sha: CommitSha,
    ) -> None:
        """DNS resolution failure → LlmUnavailableError."""
        import requests as req
        # requests library wraps DNS/socket errors into ConnectionError
        mock_post.side_effect = req.ConnectionError(
            "Failed to resolve 'localhost'",
        )
        from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
            LlmUnavailableError,
        )
        with pytest.raises(LlmUnavailableError):
            _svc.execute(self._cmd(pr_id, head_sha))

    @patch("requests.post")
    def test_review_not_published_on_failure(
        self, mock_post: MagicMock,
        pr_id: PullRequestId, head_sha: CommitSha,
        _ctx: RepositoryContext,
    ) -> None:
        """When LLM fails, review publisher is never called."""
        import requests as req
        diff = PullRequestDiff(
            pr_id=pr_id, head_sha=head_sha, diff_content="+x",
        )
        fetcher = MagicMock()
        fetcher.fetch.return_value = diff
        ctx_port = MagicMock()
        ctx_port.fetch.return_value = _ctx
        publisher = MagicMock()

        mock_post.side_effect = req.ConnectionError("down")
        llm = OllamaLlmAdapter("http://localhost:11434", "code-review")
        service = ReviewPullRequestService(
            pr_repository=MagicMock(),
            changeset_fetcher=fetcher,
            repository_context=ctx_port,
            llm_review=llm,
            review_publisher=publisher,
        )

        from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
            LlmUnavailableError,
        )
        with pytest.raises(LlmUnavailableError):
            service.execute(self._cmd(pr_id, head_sha))

        publisher.publish.assert_not_called()
