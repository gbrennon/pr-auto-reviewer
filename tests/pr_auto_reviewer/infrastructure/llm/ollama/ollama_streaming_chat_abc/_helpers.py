"""Shared helpers, fixtures, and imports for the split test modules."""

from pr_auto_reviewer.infrastructure.llm.ollama.ollama_streaming_chat_abc import (
    OllamaReviewStream,
)
from pr_auto_reviewer.infrastructure.llm.ollama.ollama_streaming_chat_impl import (
    OllamaStreamingChatClient,
)


def _client() -> OllamaStreamingChatClient:
    return OllamaStreamingChatClient(model="code-review:latest", host="http://localhost:11434")


REVIEW = {
    "verdict": "approved",
    "reason": "Solid change.",
    "summary": "No issues.",
    "items": [{"file": "a.py", "severity": "major", "description": "unused import"}],
    "suggestions": ["s1"],
    "praise": ["p1"],
}


__all__ = ['REVIEW', 'OllamaReviewStream', 'OllamaStreamingChatClient', '_client']
