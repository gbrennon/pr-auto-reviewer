"""Fake Ollama streaming chat ABC for tests - no ABC constraint."""

from __future__ import annotations


class FakeOllamaStreamingChatABC:
    """Fake implementation of OllamaStreamingChatABC for testing."""

    def __init__(self) -> None:
        self._model: str = "test-model"
        self._host: str = "http://localhost:11434"
        self._json_schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "verdict": {"type": "string"},
                "reason": {"type": "string"},
                "summary": {"type": "string"},
            },
        }
        self.send_message_calls: list[tuple[str, Any]] = []
        self.start_review_calls: list[tuple[str, int, str]] = []

    @property
    def model(self) -> str:
        return self._model

    @property
    def host(self) -> str:
        return self._host

    @property
    def json_schema(self) -> dict[str, Any]:
        return self._json_schema

    def send_message(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
        self.send_message_calls.append((message, conversation_history))
        return '{"verdict": "commented", "reason": "test", "summary": "", "suggestions": [], "items": [], "praise": []}'

    async def start_review(
        self,
        repo_path: str,
        pr_number: int,
        diff_content: str,
    ) -> str:
        self.start_review_calls.append((repo_path, pr_number, diff_content))
        return '{"verdict": "commented", "reason": "test", "summary": "", "suggestions": [], "items": [], "praise": []}'

    def parse_streaming_response(
        self, raw_lines: list[str], model: str
    ) -> tuple[list[dict[str, Any]] | None, dict[str, Any]]:
        import json
        accumulated = "".join(raw_lines)
        try:
            data = json.loads(accumulated)
        except json.JSONDecodeError:
            data = {
                "verdict": "commented",
                "reason": "failed to decode JSON",
                "summary": "",
                "suggestions": [],
                "praise": [],
            }
        items = data.get("items") or data.get("findings") or data.get("issues")
        metadata = {
            "verdict": data.get("verdict", "commented"),
            "reason": data.get("reason", ""),
            "summary": data.get("summary", ""),
            "suggestions": data.get("suggestions", []),
            "praise": data.get("praise", []),
        }
        return items, metadata


class FakeOllamaReviewStream:
    """Fake review stream for testing."""

    def __init__(self) -> None:
        self.turn_number: int = 1
        self.content: str = ""
        self.kind: str = "initial"
        self._parsed: dict[str, Any] | None = None
        self._items: list[dict[str, Any]] | None = None
        self._metadata: dict[str, Any] = {
            "verdict": "commented",
            "reason": "",
            "summary": "",
            "suggestions": [],
            "praise": [],
        }

    @property
    def parsed(self) -> dict[str, Any] | None:
        return self._parsed

    @property
    def items(self) -> list[dict[str, Any]] | None:
        return self._items

    @property
    def metadata(self) -> dict[str, Any]:
        return self._metadata

    def advance(self, content: str, kind: str) -> None:
        self.content += content
        self.kind = kind
        if kind == "complete":
            import json
            try:
                self._parsed = json.loads(self.content)
                self._items = self._parsed.get("items") or self._parsed.get("findings") or self._parsed.get("issues")
                self._metadata = {
                    "verdict": self._parsed.get("verdict", "commented"),
                    "reason": self._parsed.get("reason", ""),
                    "summary": self._parsed.get("summary", ""),
                    "suggestions": self._parsed.get("suggestions", []),
                    "praise": self._parsed.get("praise", []),
                }
            except json.JSONDecodeError:
                pass