"""Behavioral tests for OllamaStreamingLlmAdapter."""

from pr_auto_reviewer.domain.fragments.entities.composed_prompt import (
    ComposedPrompt,
)
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.repository_context import (
    RepositoryContext,
)
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.llm.ollama.ollama_streaming_llm_adapter import (
    OllamaStreamingLlmAdapter,
)

REVIEW_TEXT = "## Verdict\napproved\n\n## Summary\nok\n\n## Items\nNone"


class TestOllamaStreamingLlmAdapter:
    """Exercises the LlmReviewPort adapter orchestration."""

    def test_review_prompt_when_send_succeeds_then_returns_code_review(self, monkeypatch) -> None:
        adapter = OllamaStreamingLlmAdapter(
            host="http://localhost:11434", model="code-review:latest"
        )
        calls: list[str] = []

        def stub_send(message: str) -> str:
            calls.append(message)
            return REVIEW_TEXT

        monkeypatch.setattr(adapter._client, "send_message", stub_send)
        prompt = ComposedPrompt(content="analyze the diff", fragments_used=[], total_tokens=10)

        review = adapter.review_prompt(prompt)

        assert isinstance(review, CodeReview)
        assert review.verdict == ReviewVerdict.APPROVED
        assert calls == ["analyze the diff"]

    def test_review_prompt_clients_constructed(self) -> None:
        adapter = OllamaStreamingLlmAdapter(
            host="http://localhost:11434/", model="code-review:latest", timeout=5
        )

        assert adapter._client.host == "http://localhost:11434"
        assert adapter._client.model == "code-review:latest"
        assert adapter._parser is not None

    def test_review_when_send_succeeds_then_returns_code_review(self, monkeypatch) -> None:
        adapter = OllamaStreamingLlmAdapter(
            host="http://localhost:11434", model="code-review:latest"
        )

        def stub_send(message: str) -> str:
            return REVIEW_TEXT

        monkeypatch.setattr(adapter._client, "send_message", stub_send)
        diff = PullRequestDiff(
            pr_id=PullRequestId(repository="owner/repo", number=1),
            head_sha=CommitSha("a" * 40),
            diff_content="diff --git a/test.py b/test.py\n+new line\n",
        )
        context = RepositoryContext(
            architecture_hint="python",
            conventions=None,
            repository_structure="standard",
            pr_title="Test PR",
            pr_description="Test description",
            python_version="3.12",
        )

        review = adapter.review(diff, context)

        assert isinstance(review, CodeReview)
        assert review.verdict == ReviewVerdict.APPROVED