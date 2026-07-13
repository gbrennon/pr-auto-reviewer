"""Tests for LlamaCppAdapter using captured llama.cpp response fixtures.

Uses dependency injection via ``_http_post`` — no monkeypatching.
"""

import logging
from pathlib import Path

import pytest

from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.llama_cpp_adapter import LlamaCppAdapter


@pytest.fixture
def adapter() -> LlamaCppAdapter:
    """Create LlamaCppAdapter with test host."""
    return LlamaCppAdapter("http://localhost:8080")


@pytest.fixture
def sample_diff() -> PullRequestDiff:
    """Create a sample diff from fixture file."""
    fixture_path = (
        Path(__file__).parents[3] / "fixtures" / "diffs" / "sample-ollama.diff"
    )
    return PullRequestDiff(
        pr_id=None,
        head_sha=None,
        diff_content=fixture_path.read_text(),
    )


@pytest.fixture
def sample_context() -> RepositoryContext:
    """Create a sample review context."""
    return RepositoryContext(
        architecture_hint="Layered architecture",
        conventions="Use type hints",
        repository_structure="src/\n  main.py\n  utils/",
    )


class TestLlamaCppAdapter:
    """Tests for LlamaCppAdapter using captured fixture data.

    All tests inject a fake HTTP POST callable via ``_http_post`` rather
    than monkeypatching ``requests.post`` — the adapter calls
    ``self._post(...)`` which resolves to the injected callable.
    """

    # ── review(diff, context) tests ──────────────────────────────────────

    def test_review_returns_code_review(
        self,
        adapter: LlamaCppAdapter,
        sample_diff: PullRequestDiff,
        sample_context: RepositoryContext,
        llama_cpp_fake_post,
    ) -> None:
        """Returns CodeReview from llama.cpp chat-completion response."""
        adapter._http_post = llama_cpp_fake_post

        result = adapter.review(sample_diff, sample_context)

        assert isinstance(result, CodeReview)
        assert result.verdict == ReviewVerdict.CHANGES_REQUESTED

    def test_review_returns_approved_when_no_issues(
        self,
        adapter: LlamaCppAdapter,
        sample_diff: PullRequestDiff,
        sample_context: RepositoryContext,
        llama_cpp_fake_post_approved,
    ) -> None:
        """Returns APPROVED verdict when model finds no issues."""
        adapter._http_post = llama_cpp_fake_post_approved

        result = adapter.review(sample_diff, sample_context)

        assert isinstance(result, CodeReview)
        assert result.verdict == ReviewVerdict.APPROVED

    def test_review_raises_on_request_error(
        self,
        adapter: LlamaCppAdapter,
        sample_diff: PullRequestDiff,
        sample_context: RepositoryContext,
        llama_cpp_fake_post_error,
    ) -> None:
        """Raises LlmUnavailableError on connection failure."""
        adapter._http_post = llama_cpp_fake_post_error

        with pytest.raises(Exception):
            adapter.review(sample_diff, sample_context)

    def test_review_raises_on_invalid_json(
        self,
        adapter: LlamaCppAdapter,
        sample_diff: PullRequestDiff,
        sample_context: RepositoryContext,
        llama_cpp_fake_post_invalid_json,
    ) -> None:
        """Raises LlmUnavailableError on invalid JSON response."""
        adapter._http_post = llama_cpp_fake_post_invalid_json

        with pytest.raises(Exception):
            adapter.review(sample_diff, sample_context)

    def test_review_raises_on_empty_choices(
        self,
        adapter: LlamaCppAdapter,
        sample_diff: PullRequestDiff,
        sample_context: RepositoryContext,
        llama_cpp_fake_post_empty,
    ) -> None:
        """Raises LlmUnavailableError when choices list is empty."""
        adapter._http_post = llama_cpp_fake_post_empty

        with pytest.raises(Exception):
            adapter.review(sample_diff, sample_context)

    # ── request inspection tests ─────────────────────────────────────────

    def test_sends_request_to_chat_completions_endpoint(
        self,
        adapter: LlamaCppAdapter,
        sample_diff: PullRequestDiff,
        sample_context: RepositoryContext,
        llama_cpp_fake_post,
    ) -> None:
        """Sends POST to /v1/chat/completions with chat message format."""
        called_urls: list[str] = []
        called_payloads: list[dict] = []

        def _capture_post(url, *, json=None, timeout=None, **kwargs):
            called_urls.append(url)
            called_payloads.append(json)
            return llama_cpp_fake_post(url, json=json, timeout=timeout)

        adapter._http_post = _capture_post

        adapter.review(sample_diff, sample_context)

        assert any("/v1/chat/completions" in u for u in called_urls), (
            f"Expected /v1/chat/completions in URLs, got: {called_urls}"
        )
        assert len(called_payloads) > 0
        payload = called_payloads[0]
        assert "messages" in payload
        assert not payload.get("stream", True)

    def test_debug_logs_request_payload_when_debug_enabled(
        self,
        adapter: LlamaCppAdapter,
        sample_diff: PullRequestDiff,
        sample_context: RepositoryContext,
        llama_cpp_fake_post,
        caplog,
    ) -> None:
        """Logs request payload details when DEBUG logging is enabled."""
        adapter._http_post = llama_cpp_fake_post
        caplog.set_level(logging.DEBUG, logger="pr_auto_reviewer.infrastructure.llm")

        adapter.review(sample_diff, sample_context)

        log_text = "\n".join(caplog.messages)
        assert "user_chars=" in log_text or "USER PROMPT" in log_text

    # ── review_prompt tests ──────────────────────────────────────────────

    def test_system_prompt_separated_to_system_message(
        self,
        adapter: LlamaCppAdapter,
        llama_cpp_fake_post_approved,
    ) -> None:
        """When prompt contains the fragment separator, system text becomes
        a system role message."""
        from pr_auto_reviewer.domain.fragments.entities.composed_prompt import (
            ComposedPrompt,
        )

        captured_payload: dict | None = None

        def _capture_post(url, *, json=None, timeout=None, **kwargs):
            nonlocal captured_payload
            captured_payload = json
            return llama_cpp_fake_post_approved(url, json=json, timeout=timeout)

        adapter._http_post = _capture_post

        prompt = ComposedPrompt(
            content="You are a code reviewer.\n\n---\n\nReview this diff:\n+foo",
            total_tokens=30,
            fragments_used=["reviewer-system-prompt", "diff-fragment"],
        )
        adapter.review_prompt(prompt)

        assert captured_payload is not None
        messages = captured_payload["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert "code reviewer" in messages[0]["content"].lower()
        assert messages[1]["role"] == "user"
        assert "Review this diff" in messages[1]["content"]

    def test_single_message_when_no_separator(
        self,
        adapter: LlamaCppAdapter,
        llama_cpp_fake_post_approved,
    ) -> None:
        """When prompt has no separator, only a user message is sent."""
        from pr_auto_reviewer.domain.fragments.entities.composed_prompt import (
            ComposedPrompt,
        )

        captured_payload: dict | None = None

        def _capture_post(url, *, json=None, timeout=None, **kwargs):
            nonlocal captured_payload
            captured_payload = json
            return llama_cpp_fake_post_approved(url, json=json, timeout=timeout)

        adapter._http_post = _capture_post

        prompt = ComposedPrompt(
            content="Review this diff",
            total_tokens=10,
            fragments_used=["diff-fragment"],
        )
        adapter.review_prompt(prompt)

        assert captured_payload is not None
        messages = captured_payload["messages"]
        assert len(messages) == 1
        assert messages[0]["role"] == "user"

    def test_backend_name_is_llama_cpp(self, adapter: LlamaCppAdapter) -> None:
        """Adapter identifies itself as llama.cpp."""
        assert adapter.backend_name == "llama.cpp"
