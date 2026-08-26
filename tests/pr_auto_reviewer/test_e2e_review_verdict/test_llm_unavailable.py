from ._helpers import *


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
