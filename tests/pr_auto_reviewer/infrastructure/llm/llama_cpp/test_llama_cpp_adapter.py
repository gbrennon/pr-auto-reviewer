"""Tests for LlamaCppAdapter."""

from __future__ import annotations

import json
from typing import Any

import pytest
import requests

from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import (
    ComposedPrompt,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_diff import (
    PullRequestDiff,
)
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.repository_context import (
    RepositoryContext,
)
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.llama_cpp.llama_cpp_adapter import (
    LlamaCppAdapter,
)


class _FakeHttpResponse:
    def __init__(self, json_data: dict[str, Any], status_code: int = 200) -> None:
        self._json_data = json_data
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests.HTTPError(f"Status {self.status_code}")

    def json(self) -> dict[str, Any]:
        return self._json_data


def _sample_review_payload() -> dict[str, Any]:
    review_json = {
        "verdict": "approved",
        "summary": "Everything looks good",
        "items": [],
        "reason": "All checks passed",
    }
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": json.dumps(review_json),
                }
            }
        ],
        "usage": {"completion_tokens": 42},
        "timings": {"predicted_ms": 1500.0},
    }


def _sample_diff() -> PullRequestDiff:
    return PullRequestDiff(
        pr_id=PullRequestId(repository="owner/repo", number=1),
        head_sha=CommitSha("a" * 40),
        diff_content="diff --git a/foo.py b/foo.py\n+print('hello')\n",
    )


def _sample_context() -> RepositoryContext:
    return RepositoryContext(architecture_hint="Hexagonal")


class TestLlamaCppAdapter:
    def test_build_messages_splits_on_separator(self) -> None:
        adapter = LlamaCppAdapter()
        prompt = "System instructions\n\n---\n\nUser request"
        messages = adapter._build_messages(prompt)

        assert len(messages) == 2
        assert messages[0] == {"role": "system", "content": "System instructions"}
        assert messages[1] == {"role": "user", "content": "User request"}

    def test_build_messages_without_separator(self) -> None:
        adapter = LlamaCppAdapter()
        prompt = "Plain prompt without separator"
        messages = adapter._build_messages(prompt)

        assert len(messages) == 1
        assert messages[0] == {"role": "user", "content": prompt}

    def test_review_returns_parsed_code_review(self) -> None:
        def fake_post(*_args: Any, **_kwargs: Any) -> _FakeHttpResponse:
            return _FakeHttpResponse(_sample_review_payload())

        adapter = LlamaCppAdapter(http_post=fake_post)
        review = adapter.review(_sample_diff(), _sample_context())

        assert isinstance(review, CodeReview)
        assert review.verdict == ReviewVerdict.APPROVED
        assert review.summary == "Everything looks good"

    def test_review_falls_back_to_reasoning_content(self) -> None:
        review_json = {
            "verdict": "approved",
            "summary": "Reasoned review",
            "items": [],
            "reason": "Clear",
        }
        payload = {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "",
                        "reasoning_content": json.dumps(review_json),
                    }
                }
            ],
            "usage": {"completion_tokens": 10},
        }

        def fake_post(*_args: Any, **_kwargs: Any) -> _FakeHttpResponse:
            return _FakeHttpResponse(payload)

        adapter = LlamaCppAdapter(http_post=fake_post)
        review = adapter.review(_sample_diff(), _sample_context())

        assert review.verdict == ReviewVerdict.APPROVED
        assert review.summary == "Reasoned review"

    def test_review_raises_on_empty_response(self) -> None:
        empty_payload = {"choices": [{"message": {"content": ""}}]}

        def fake_post(*_args: Any, **_kwargs: Any) -> _FakeHttpResponse:
            return _FakeHttpResponse(empty_payload)

        adapter = LlamaCppAdapter(http_post=fake_post)
        with pytest.raises(LlmUnavailableError):
            adapter.review(_sample_diff(), _sample_context())

    def test_review_raises_on_network_error(self) -> None:
        def fake_post(*_args: Any, **_kwargs: Any) -> Any:
            raise requests.ConnectionError("Connection refused")

        adapter = LlamaCppAdapter(http_post=fake_post)
        with pytest.raises(LlmUnavailableError):
            adapter.review(_sample_diff(), _sample_context())

    def test_review_prompt_returns_code_review(self) -> None:
        def fake_post(*_args: Any, **_kwargs: Any) -> _FakeHttpResponse:
            return _FakeHttpResponse(_sample_review_payload())

        adapter = LlamaCppAdapter(http_post=fake_post)
        prompt = ComposedPrompt(
            content="System prompt\n\n---\n\nUser diff",
            fragments_used=["system", "diff"],
            total_tokens=100,
        )
        review = adapter.review_prompt(prompt)

        assert isinstance(review, CodeReview)
        assert review.verdict == ReviewVerdict.APPROVED
