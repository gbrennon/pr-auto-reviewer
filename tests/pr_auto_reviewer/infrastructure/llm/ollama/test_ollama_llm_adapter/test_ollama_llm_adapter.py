from ._helpers import *


class TestOllamaLlmAdapter:
    """Tests for OllamaLlmAdapter."""

    def test_review_sends_request_to_ollama(
        self, monkeypatch, adapter: OllamaLlmAdapter,
        sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        ollama_fake_post,
    ) -> None:
        """Sends POST request to Ollama with correct payload."""
        monkeypatch.setattr(_requests, "post", ollama_fake_post)

        result = adapter.review(sample_diff, sample_context)

        assert isinstance(result, CodeReview)

    def test_review_returns_code_review(
        self, monkeypatch, adapter: OllamaLlmAdapter,
        sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        ollama_fake_post,
    ) -> None:
        """Returns CodeReview from Ollama response."""
        import requests as _requests
        monkeypatch.setattr(_requests, "post", ollama_fake_post)

        result = adapter.review(sample_diff, sample_context)

        assert isinstance(result, CodeReview)
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1
        assert result.items[0].severity == ItemSeverity.MAJOR

    def test_review_raises_on_request_error(
        self, monkeypatch, adapter: OllamaLlmAdapter,
        sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        ollama_fake_post_error,
    ) -> None:
        """Raises LlmUnavailableError on request failure."""
        import requests as _requests
        monkeypatch.setattr(_requests, "post", ollama_fake_post_error)

        with pytest.raises(LlmUnavailableError):
            adapter.review(sample_diff, sample_context)

    def test_debug_logs_request_payload_when_debug_enabled(
        self, monkeypatch, adapter: OllamaLlmAdapter,
        sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        ollama_fake_post, caplog,
    ) -> None:
        import requests as _requests
        monkeypatch.setattr(_requests, "post", ollama_fake_post)

        caplog.set_level(logging.DEBUG)
        adapter.review(sample_diff, sample_context)

        request_logs = [
            r.message for r in caplog.records
            if "Ollama request payload" in r.message
        ]
        assert len(request_logs) == 1
        assert "model=code-review" in request_logs[0]
        assert "prompt_chars=" in request_logs[0]

    def test_debug_logs_review_summary_when_debug_enabled(
        self, monkeypatch, adapter: OllamaLlmAdapter,
        sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        ollama_fake_post, caplog,
    ) -> None:
        import requests as _requests
        monkeypatch.setattr(_requests, "post", ollama_fake_post)

        caplog.set_level(logging.DEBUG)
        adapter.review(sample_diff, sample_context)

        summary_logs = [
            r.message for r in caplog.records
            if "OLLAMA REVIEW SUMMARY" in r.message
        ]
        assert len(summary_logs) == 1
        summary = summary_logs[0]
        assert "host=" in summary
        assert "model=" in summary
        assert "prompt=" in summary
        assert "verdict=" in summary
        assert "items=" in summary
        assert "summary=" in summary

    def test_review_summary_not_logged_at_info_level(
        self, monkeypatch, adapter: OllamaLlmAdapter,
        sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        ollama_fake_post, caplog,
    ) -> None:
        import requests as _requests
        monkeypatch.setattr(_requests, "post", ollama_fake_post)

        caplog.set_level(logging.INFO)
        adapter.review(sample_diff, sample_context)

        summary_logs = [
            r.message for r in caplog.records
            if "OLLAMA REVIEW SUMMARY" in r.message
        ]
        assert len(summary_logs) == 0

    def test_review_raises_on_invalid_json(
        self, monkeypatch, adapter: OllamaLlmAdapter,
        sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        ollama_fake_post_invalid_json,
    ) -> None:
        """Raises LlmUnavailableError on invalid JSON."""
        import requests as _requests
        monkeypatch.setattr(_requests, "post", ollama_fake_post_invalid_json)

        with pytest.raises(LlmUnavailableError):
            adapter.review(sample_diff, sample_context)

    def test_review_handles_empty_response(
        self, monkeypatch, adapter: OllamaLlmAdapter,
        sample_diff: PullRequestDiff, sample_context: RepositoryContext,
        ollama_fake_post_empty,
    ) -> None:
        """Raises LlmUnavailableError on empty response."""
        import requests as _requests
        monkeypatch.setattr(_requests, "post", ollama_fake_post_empty)

        with pytest.raises(LlmUnavailableError):
            adapter.review(sample_diff, sample_context)


    def test_retry_succeeds_after_validation_failure(
        self, monkeypatch, sample_diff: PullRequestDiff,
        sample_context: RepositoryContext,
    ) -> None:
        """Retry loop reprocesses when initial response fails validation.

        Simulates transient LLM quality issues: first response triggers
        diagnose_failures (empty JSON → missing verdict), correction prompt is
        built, second response passes validation.
        """
        adapter = OllamaLlmAdapter(
            "http://localhost:11434", "code-review", max_retries=3,
        )

        call_count = 0

        bad_raw = json.dumps({
            "verdict": "changes_requested",
            "issues": [{
                "file": "src/foo.py",
                "description": "bad code",
                "severity": "major",
                "type": "maintainability",
            }],
        })
        good_raw = json.dumps({
            "verdict": "changes_requested",
            "issues": [{
                "file": "src/foo.py",
                "description": "bad code",
                "severity": "major",
                "type": "maintainability",
                "current_code": "x = 1",
                "suggested_fix": "x = 2",
            }],
        })

        def fake_request_ollama(_prompt_text: str, _timeout: int):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (bad_raw, 100.0, 10, 0.5)
            return (good_raw, 100.0, 10, 0.5)

        monkeypatch.setattr(adapter, "_request_ollama", fake_request_ollama)
        monkeypatch.setattr(adapter, "_dump_prompt_to_file", lambda *_: None)
        monkeypatch.setattr("time.sleep", lambda _: None)

        result = adapter.review(sample_diff, sample_context)

        assert call_count == 2
        assert isinstance(result, CodeReview)
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1
        assert result.items[0].file_path == "src/foo.py"

    def test_retry_exhausts_attempts_when_all_validations_fail(
        self, monkeypatch, sample_diff: PullRequestDiff,
        sample_context: RepositoryContext,
    ) -> None:
        """Returns last CodeReview when every retry attempt fails validation.

        The retry loop calls _request_ollama exactly max_retries times.
        The last parsed CodeReview (with failures) is returned — the caller
        is responsible for deciding how to handle it.
        """
        max_retries = 3
        adapter = OllamaLlmAdapter(
            "http://localhost:11434", "code-review", max_retries=max_retries,
        )

        call_count = 0
        bad_raw = json.dumps({
            "verdict": "changes_requested",
            "issues": [{
                "file": "src/foo.py",
                "description": "bad code",
                "severity": "major",
                "type": "maintainability",
            }],
        })

        def fake_request_ollama(_prompt_text: str, _timeout: int):
            nonlocal call_count
            call_count += 1
            return (bad_raw, 100.0, 10, 0.5)

        monkeypatch.setattr(adapter, "_request_ollama", fake_request_ollama)
        monkeypatch.setattr(adapter, "_dump_prompt_to_file", lambda *_: None)
        monkeypatch.setattr("time.sleep", lambda _: None)

        result = adapter.review(sample_diff, sample_context)

        assert call_count == max_retries
        assert isinstance(result, CodeReview)
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1

