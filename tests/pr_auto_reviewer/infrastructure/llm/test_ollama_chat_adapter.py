"""Tests for OllamaChatAdapter."""

import json
import time as _time

import pytest
import requests as _requests

from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_diff import (
    PullRequestDiff,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.ollama_chat_adapter import (
    OllamaChatAdapter,
)


@pytest.fixture
def chat_adapter() -> OllamaChatAdapter:
    """Create OllamaChatAdapter with test defaults."""
    return OllamaChatAdapter(model="phi4")


@pytest.fixture
def chat_adapter_low_retries() -> OllamaChatAdapter:
    """Create OllamaChatAdapter with low retry count for faster tests."""
    return OllamaChatAdapter(model="phi4", max_retries=2)


@pytest.fixture
def sample_prompt() -> ComposedPrompt:
    """Create a sample ComposedPrompt."""
    return ComposedPrompt(
        content="Review this diff:\n```diff\n+ x = 1\n```",
        fragments_used=["frag-1"],
        total_tokens=50,
    )


class TestOllamaChatAdapter:
    """Tests for OllamaChatAdapter."""

    def test_review_prompt_returns_code_review(
        self, monkeypatch, chat_adapter: OllamaChatAdapter,
        sample_prompt: ComposedPrompt,
    ) -> None:
        """Sends /api/chat request and returns a parsed CodeReview."""
        good_response = {
            "message": {
                "content": json.dumps({
                    "issues": [{
                        "file": "src/foo.py",
                        "line": "42",
                        "severity": "major",
                        "type": "security",
                        "description": "SQL injection",
                        "current_code": "query = 'SELECT * FROM users WHERE id = ' + uid",
                        "suggested_fix": "query = 'SELECT * FROM users WHERE id = %s'",
                    }],
                    "summary": "Found one major issue",
                    "suggestions": [],
                    "praise": [],
                }),
            },
        }

        def fake_post(url: str, *, json: dict | None = None, timeout: int | None = None, **kwargs: object) -> _FakeChatResponse:
            assert "/api/chat" in url
            assert json is not None
            assert json["stream"] is False
            assert json["messages"][0]["role"] == "user"
            assert json["messages"][0]["content"] == sample_prompt.content
            return _FakeChatResponse(good_response)

        monkeypatch.setattr(_requests, "post", fake_post)

        result = chat_adapter.review_prompt(sample_prompt)

        assert isinstance(result, CodeReview)
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1
        assert result.items[0].severity == ItemSeverity.MAJOR
        assert result.items[0].file_path == "src/foo.py"

    def test_review_prompt_raises_on_request_error(
        self, monkeypatch, chat_adapter: OllamaChatAdapter,
        sample_prompt: ComposedPrompt,
    ) -> None:
        """Raises LlmUnavailableError when POST fails."""
        def fake_post(url: str, *, json: dict | None = None, timeout: int | None = None, **kwargs: object) -> _FakeChatResponse:
            raise _requests.RequestException("Connection refused")

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(_time, "sleep", lambda _: None)

        with pytest.raises(LlmUnavailableError, match="Chat request to.*failed"):
            chat_adapter.review_prompt(sample_prompt)

    def test_review_prompt_raises_on_empty_content(
        self, monkeypatch, chat_adapter: OllamaChatAdapter,
        sample_prompt: ComposedPrompt,
    ) -> None:
        """Raises LlmUnavailableError when message content is empty."""
        def fake_post(url: str, *, json: dict | None = None, timeout: int | None = None, **kwargs: object) -> _FakeChatResponse:
            return _FakeChatResponse({"message": {"content": ""}})

        monkeypatch.setattr(_requests, "post", fake_post)

        with pytest.raises(LlmUnavailableError, match="Empty response"):
            chat_adapter.review_prompt(sample_prompt)

    def test_review_prompt_raises_on_missing_message(
        self, monkeypatch, chat_adapter: OllamaChatAdapter,
        sample_prompt: ComposedPrompt,
    ) -> None:
        """Raises LlmUnavailableError when response has no message key."""
        def fake_post(url: str, *, json: dict | None = None, timeout: int | None = None, **kwargs: object) -> _FakeChatResponse:
            return _FakeChatResponse({})

        monkeypatch.setattr(_requests, "post", fake_post)

        with pytest.raises(LlmUnavailableError, match="Empty response"):
            chat_adapter.review_prompt(sample_prompt)

    def test_review_prompt_retry_success(
        self, monkeypatch,
        chat_adapter_low_retries: OllamaChatAdapter,
        sample_prompt: ComposedPrompt,
    ) -> None:
        """Retries on first failure then returns CodeReview on second attempt."""
        call_count = 0

        def fake_post(url: str, *, json: dict | None = None, timeout: int | None = None, **kwargs: object) -> _FakeChatResponse:
            import json as _json
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise _requests.RequestException("Temporary failure")
            return _FakeChatResponse({
                "message": {
                    "content": _json.dumps({
                        "issues": [{
                            "file": "src/bar.py",
                            "line": "10",
                            "severity": "minor",
                            "type": "style",
                            "description": "Use snake_case",
                            "current_code": "myVar = 1",
                            "suggested_fix": "my_var = 1",
                        }],
                        "summary": "One minor style issue",
                        "suggestions": [],
                        "praise": [],
                    }),
                },
            })

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(_time, "sleep", lambda _: None)

        result = chat_adapter_low_retries.review_prompt(sample_prompt)
        assert call_count == 2
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(result.items) == 1

    def test_review_prompt_retry_exhaustion(
        self, monkeypatch,
        chat_adapter_low_retries: OllamaChatAdapter,
        sample_prompt: ComposedPrompt,
    ) -> None:
        """Raises LlmUnavailableError after all retries exhausted."""
        call_count = 0

        def fake_post(url: str, *, json: dict | None = None, timeout: int | None = None, **kwargs: object) -> _FakeChatResponse:
            nonlocal call_count
            call_count += 1
            raise _requests.RequestException("Persistent failure")

        monkeypatch.setattr(_requests, "post", fake_post)
        monkeypatch.setattr(_time, "sleep", lambda _: None)

        with pytest.raises(LlmUnavailableError, match="Chat request to.*failed"):
            chat_adapter_low_retries.review_prompt(sample_prompt)

        assert call_count == 2

    def test_review_raises_not_implemented(
        self, chat_adapter: OllamaChatAdapter,
    ) -> None:
        """Direct review() raises NotImplementedError."""
        diff = PullRequestDiff(
            pr_id=PullRequestId(repository="test/repo", number=1),
            head_sha=CommitSha("abc123def4567890abc123def4567890abc123de"),
            diff_content="diff --git a/foo.py b/foo.py",
        )
        context = RepositoryContext(architecture_hint="Python package")

        with pytest.raises(NotImplementedError, match="fragment-based"):
            chat_adapter.review(diff, context)

    def test_review_prompt_uses_fixture_file(
        self, monkeypatch, chat_adapter: OllamaChatAdapter,
        sample_prompt: ComposedPrompt,
    ) -> None:
        """Parses a chat-response fixture file into a valid CodeReview."""
        import json as _json
        from pathlib import Path as _Path

        fixtures_dir = _Path(__file__).parent.parent.parent.parent / "fixtures" / "ollama_responses"
        raw = fixtures_dir / "chat_response.json"
        fixture_data = _json.loads(raw.read_text())

        def fake_post(url: str, *, json: dict | None = None, timeout: int | None = None, **kwargs: object) -> _FakeChatResponse:
            return _FakeChatResponse(fixture_data)

        monkeypatch.setattr(_requests, "post", fake_post)

        result = chat_adapter.review_prompt(sample_prompt)

        assert isinstance(result, CodeReview)
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED


class _FakeChatResponse:
    """Minimal fake requests.Response for OllamaChatAdapter tests."""

    def __init__(self, json_data: dict, *, status_code: int = 200) -> None:
        self._json_data = json_data
        self.status_code = status_code

    def json(self) -> dict:
        return self._json_data

    def raise_for_status(self) -> None:
        pass
