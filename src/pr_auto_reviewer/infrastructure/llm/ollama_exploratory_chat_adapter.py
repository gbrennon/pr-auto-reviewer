"""OllamaExploratoryChatAdapter — multi-turn LLM adapter with streaming and structured JSON.

Uses Ollama's ``format: "json"`` and streaming chat to let the model explore
the codebase before rendering a verdict. The JSON protocol replaces the old
``ACTION:``/``VERDICT:`` text markers with structured objects.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests

from pr_auto_reviewer.application.ports.outbound.llm_review_port import LlmReviewPort
from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.repository_context import RepositoryContext
from pr_auto_reviewer.infrastructure.llm.exploration_tool_service import (
    ExplorationToolService,
)
from pr_auto_reviewer.infrastructure.llm.review_response_parser import ReviewResponseParser

logger = logging.getLogger(__name__)

_MAX_TURNS = 20


class OllamaExploratoryChatAdapter(LlmReviewPort):
    """Multi-turn LLM adapter that lets the model explore before reviewing.

    The model is given a system prompt teaching it to use structured JSON
    tool calls (``{"action": "...", "args": "..."}``) and emit a final
    ``{"verdict": "...", ...}`` object.  Each tool call is executed against
    the cloned repository and the result is injected back into the
    conversation.

    Single-pass review is used when ``ComposedPrompt.repo_path`` is empty.
    """

    def __init__(
        self,
        model: str,
        host: str = "http://localhost:11434",
        ollama_timeout: int = 120,
        max_retries: int = 5,
    ) -> None:
        self._model = model
        self._host = host.rstrip("/")
        self._timeout = ollama_timeout
        self._max_retries = max_retries
        self._parser = ReviewResponseParser()

    def review(
        self,
        diff: PullRequestDiff,
        context: RepositoryContext,
    ) -> CodeReview:
        raise NotImplementedError(
            "Direct review() is not supported. "
            "Use the fragment-based flow via review_prompt()."
        )

    def review_prompt(self, composed: ComposedPrompt) -> CodeReview:
        repo_path = composed.repo_path
        if not repo_path or not repo_path.strip():
            logger.info(
                "No repo_path in ComposedPrompt — falling back to single-pass review"
            )
            return self._single_pass(composed)

        return self._multi_turn(composed, repo_path.strip())

    def _single_pass(self, composed: ComposedPrompt) -> CodeReview:
        messages: list[dict[str, Any]] = [
            {"role": "user", "content": composed.content},
        ]
        content = self._stream_chat(messages)
        if not content:
            raise LlmUnavailableError("Empty response from LLM chat API")
        return self._parser.parse(content, self._model)

    def _multi_turn(self, composed: ComposedPrompt, repo_path: str) -> CodeReview:
        tool_service = ExplorationToolService(repo_path)
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": composed.content},
            {
                "role": "user",
                "content": (
                    f"The repository is cloned at this path on your filesystem:\n\n"
                    f"  {repo_path}\n\n"
                    f"All tool paths (read_file, list_directory) are RELATIVE to "
                    f"the repository root. Use \".\" for the root directory.\n\n"
                    f"Respond with JSON: {{\"action\": \"...\", \"args\": \"...\"}} "
                    f"to explore, or {{\"verdict\": \"...\", ...}} when ready."
                ),
            },
        ]

        for turn in range(_MAX_TURNS):
            logger.debug("Turn %d/%d", turn + 1, _MAX_TURNS)
            content = self._stream_chat(messages)
            if not content:
                raise LlmUnavailableError(
                    f"Empty response from LLM chat API at turn {turn + 1}"
                )

            parsed: dict[str, Any]
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                logger.warning(
                    "Turn %d: model returned non-JSON content (len=%d), appending as-is",
                    turn + 1,
                    len(content),
                )
                messages.append({"role": "assistant", "content": content})
                continue

            if "verdict" in parsed:
                logger.debug("Got verdict at turn %d", turn + 1)
                return self._parser.parse(content, self._model)

            action = parsed.get("action", "")
            if action:
                args = parsed.get("args", "")
                logger.debug("Executing tool: %s %s", action, args)
                result = tool_service.execute(action, args)
                messages.append({"role": "assistant", "content": content})
                messages.append(
                    {"role": "user", "content": json.dumps(result)},
                )
                continue

            logger.debug("No action or verdict found — appending and continuing")
            messages.append({"role": "assistant", "content": content})

        raise LlmUnavailableError(
            f"Exceeded max turns ({_MAX_TURNS}) without a verdict"
        )

    def _stream_chat(self, messages: list[dict[str, Any]]) -> str:
        url = f"{self._host}/api/chat"
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "format": "json",
        }
        for attempt in range(self._max_retries):
            try:
                http_response = requests.post(
                    url,
                    json=payload,
                    timeout=self._timeout,
                    stream=True,
                )
                http_response.raise_for_status()
                content_parts: list[str] = []
                for line in http_response.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    chunk: dict[str, Any] = json.loads(line)
                    content_parts.append(
                        chunk.get("message", {}).get("content", "")
                    )
                    if chunk.get("done"):
                        break
                return "".join(content_parts)
            except (requests.RequestException, json.JSONDecodeError) as exc:
                if attempt == self._max_retries - 1:
                    raise LlmUnavailableError(
                        f"Chat request to {url} failed after "
                        f"{self._max_retries} attempts: {exc}"
                    ) from exc
                logger.warning(
                    "Chat attempt %d/%d failed, retrying...",
                    attempt + 1,
                    self._max_retries,
                )
                time.sleep(2**attempt)
        raise LlmUnavailableError("All chat requests exhausted")
