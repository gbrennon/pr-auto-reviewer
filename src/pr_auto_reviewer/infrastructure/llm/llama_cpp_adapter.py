"""LlamaCppAdapter — implements LlmReviewPort using a local llama.cpp server."""

import json
import logging
import time
from typing import Any

import requests

from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError
from pr_auto_reviewer.infrastructure.llm.base_llm_adapter import BaseLlmAdapter

logger = logging.getLogger(__name__)

_SEP = "=" * 72


class LlamaCppAdapter(BaseLlmAdapter):
    """Call a local llama.cpp server (OpenAI-compatible API) to review a PR diff.

    llama.cpp's ``llama-server`` exposes an OpenAI-compatible
    ``/v1/chat/completions`` endpoint.  It serves a single model loaded at
    startup, so ``model`` is optional and only passed through when the server
    was started with ``--alias``.
    """

    backend_name = "llama.cpp"

    def __init__(
        self,
        host: str,
        model: str = "",
        compose_review_prompt: object | None = None,
        fragment_selector: object | None = None,
        fragment_composer: object | None = None,
        max_tokens: int = 9999,
        max_file_chars: int = 3000,
        max_files: int = 10,
        max_structure_lines: int = 100,
        use_compact_template: bool = False,
    ) -> None:
        super().__init__(
            host=host,
            model=model or "local-model",
            compose_review_prompt=compose_review_prompt,
            fragment_selector=fragment_selector,
            fragment_composer=fragment_composer,
            max_tokens=max_tokens,
            max_file_chars=max_file_chars,
            max_files=max_files,
            max_structure_lines=max_structure_lines,
            use_compact_template=use_compact_template,
        )

    def _send_request(
        self,
        prompt_text: str,
        timeout: int,
    ) -> tuple[str, float, Any, float]:
        """Send one request to llama.cpp and return raw response details."""
        t0 = time.monotonic()
        logger.info("Calling llama.cpp at %s", self._host)
        logger.info("Prompt built: %d chars", len(prompt_text))

        SEP = "\n\n---\n\n"
        system_text = ""
        user_text = prompt_text
        if SEP in prompt_text:
            parts = prompt_text.split(SEP, 1)
            system_text = parts[0]
            user_text = parts[1]

        messages: list[dict[str, str]] = []
        if system_text:
            messages.append({"role": "system", "content": system_text})
        messages.append({"role": "user", "content": user_text})

        req: dict[str, Any] = {
            "messages": messages,
            "temperature": 0.2,
            "max_tokens": self._max_tokens,
            "stream": False,
        }

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "llama.cpp request payload: messages=%d system_chars=%d user_chars=%d",
                len(messages),
                len(system_text),
                len(user_text),
            )
            logger.debug(_SEP)
            if system_text:
                logger.debug(
                    "SYSTEM PROMPT (%d chars):\n%s", len(system_text), system_text[:500]
                )
                logger.debug(_SEP)
            logger.debug(
                "USER PROMPT (%d chars):\n%s", len(user_text), user_text[:1000]
            )
            logger.debug(_SEP)

        try:
            response = self._post(
                f"{self._host}/v1/chat/completions",
                json=req,
                timeout=timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("llama.cpp request failed: %s", exc)
            raise LlmUnavailableError(
                f"llama.cpp @ {self._host} unreachable or error: {exc}"
            ) from exc

        t1 = time.monotonic()
        response_ms = (t1 - t0) * 1000

        try:
            body: dict[str, Any] = response.json()
        except json.JSONDecodeError as exc:
            logger.error("llama.cpp returned invalid JSON: %s", exc)
            raise LlmUnavailableError(
                f"llama.cpp returned invalid JSON: {exc}"
            ) from exc

        choices: list[dict[str, Any]] = body.get("choices", [])
        if not choices:
            logger.error("llama.cpp returned no choices in response")
            raise LlmUnavailableError(
                "llama.cpp returned an empty response — model may have failed silently."
            )

        raw_text: str = choices[0].get("message", {}).get("content", "")
        if not raw_text:
            logger.error("llama.cpp returned empty content")
            raise LlmUnavailableError(
                "llama.cpp returned an empty response — model may have failed silently."
            )

        usage: dict[str, Any] = body.get("usage", {})
        eval_count = usage.get("completion_tokens", "?")
        eval_duration = body.get("timings", {}).get("predicted_ms", 0) / 1000.0

        logger.info(
            "llama.cpp response: %d chars, %s tokens, %.1fs eval, %.0fms wall",
            len(raw_text),
            eval_count,
            eval_duration,
            response_ms,
        )

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(_SEP)
            logger.debug(
                "FULL LLAMA.CPP RESPONSE (%d chars):\n%s", len(raw_text), raw_text
            )
            logger.debug(_SEP)

        return raw_text, response_ms, eval_count, eval_duration
