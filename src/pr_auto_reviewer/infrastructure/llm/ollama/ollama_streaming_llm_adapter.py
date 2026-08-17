"""Ollama streaming LLM adapter — implements LlmReviewPort using Ollama streaming chat.

Wraps :class:`OllamaStreamingChatClient` to conform to the ``LlmReviewPort`` protocol,
so the existing review service flow (``ReviewPullRequestService`` → ``review_prompt`` →
``ReviewResponseParser``) continues to work without modification.

Key differences from the old ``OllamaLlmAdapter``:
* Uses ``/api/chat`` endpoint with ``stream: True`` and ``format: <json_schema>``
* Engine-level GBNF logit masking guarantees valid JSON output — no prompt-time
  "respond-only-JSON" instructions needed, no post-hoc regex/fence stripping.
* The stream accumulates JSON‑lines; the accumulated text is fed to
  ``ReviewResponseParser.parse()`` (which already handles prose→markdown fallback
  and enables ``suggested_fix`` extraction from code blocks/fix headers).
"""

from __future__ import annotations

import logging

from pr_auto_reviewer.application.ports.outbound.llm_review_port import LlmReviewPort
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext
from pr_auto_reviewer.infrastructure.llm.review_response_parser import (
    ReviewResponseParser,
)

from .ollama_streaming_chat_impl import OllamaStreamingChatClient

logger = logging.getLogger(__name__)


class OllamaStreamingLlmAdapter(LlmReviewPort):
    """Adapter implementing ``LlmReviewPort`` using ``OllamaStreamingChatClient``.

    The ``review_prompt`` method sends the prompt content to Ollama via
    ``send_message()`` (single‑call, blocking) and then parses the full response
    text through ``ReviewResponseParser`` — exactly what the existing service
    flow expects.
    """

    def __init__(
        self,
        *,
        host: str,
        model: str,
        timeout: int = 120,
    ) -> None:
        self._client = OllamaStreamingChatClient(
            model=model,
            host=host.rstrip("/"),
            timeout=timeout,
        )
        self._parser = ReviewResponseParser()

    # ---- LlmReviewPort protocol ----

    def review_prompt(self, prompt: ComposedPrompt) -> CodeReview:
        """Send a composed prompt to Ollama via streaming chat and return a CodeReview.

        The prompt ``content`` (already assembled by ``ReviewContextFactory``) is
        sent to the model using ``send_message()``.  The returned text is then
        passed to ``ReviewResponseParser.parse()`` — enabling ``suggested_fix``
        extraction from code blocks or ``**Fix**``/``**Suggested Fix**``/
        ``**Improved Code```` headers via the prose parser path that was added
        to ``review_response_parser.py`` earlier.

        Args:
            prompt: A fully assembled prompt ready for LLM consumption.

        Returns:
            The parsed code review.
        """
        logger.info(
            "Streaming review with composed prompt: %d chars, %d tokens",
            len(prompt.content),
            prompt.total_tokens,
        )

        # Send the prompt content as a single message and get the full response
        raw_text = self._client.send_message(prompt.content)

        logger.info(
            "Got %d chars from Ollama streaming chat", len(raw_text)
        )

        return self._parser.parse(raw_text, "code-review:latest")

    # The ``review`` method (deprecated in the protocol) is provided for
    # compatibility — it builds a prompt via PromptBuilder and calls Ollama.
    def review(  # type: ignore[override]
        self,
        diff: PullRequestDiff,
        context: RepositoryContext,
    ) -> CodeReview:
        from pr_auto_reviewer.infrastructure.llm.prompt_builder import PromptBuilder

        prompt_builder = PromptBuilder()
        prompt_str = prompt_builder.build(diff, context)
        # Fall back to the old single‑call path using the same parser
        raw_text = self._client.send_message(prompt_str)
        return self._parser.parse(raw_text, "")