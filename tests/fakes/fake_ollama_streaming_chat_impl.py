"""Fake Ollama streaming chat implementation for tests."""

from __future__ import annotations

import asyncio
from typing import Any


class FakeOllamaStreamingChatImpl:
    """Fake Ollama streaming chat client that simulates HTTP calls without making them."""

    def __init__(
        self,
        *,
        model: str,
        host: str,
        timeout: int = 120,
    ) -> None:
        self._model = model
        self._host = host.rstrip("/")
        self._timeout = timeout
        self.send_message_calls: list[tuple[str, Any]] = []
        self.start_review_calls: list[tuple[str, int, str]] = []

    # ---- send_message ----

    def send_message(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
        """Return fake response text without making HTTP calls."""
        self.send_message_calls.append((message, conversation_history))
        return '{"verdict": "commented", "reason": "test", "summary": "", "suggestions": [], "items": [], "praise": []}'

    # ---- start_review ----

    async def start_review(
        self,
        repo_path: str,
        pr_number: int,
        diff_content: str,
    ) -> str:
        """Async generator that yields review turns without making HTTP calls."""
        self.start_review_calls.append((repo_path, pr_number, diff_content))
        # Yield a single complete turn with parsed JSON
        yield {
            "content": '{"verdict": "commented", "reason": "test", "summary": "", "suggestions": [], "items": [], "praise": []}',
            "kind": "complete",
            "turn_number": 1,
            "parsed": {
                "verdict": "commented",
                "reason": "test",
                "summary": "",
                "suggestions": [],
                "items": [],
                "praise": [],
            },
        }

        # Yield any intermediate turns (none in fake mode)