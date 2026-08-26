from ._shared import *


class OllamaReviewStream:
    """Container for the asynchronous review stream yielded by
    ``OllamaStreamingChatABC.start_review()``.

    Holds the accumulated state as the review progresses across multiple
    LLM turns, and provides a convenient way to retrieve the final
    parsed result.
    """

    def __init__(self) -> None:
        self.turn_number: int = 1
        self.content: str = ""
        self.kind: str = "initial"
        self.parsed: dict[str, Any] | None = None
        self._items: list[dict[str, Any]] | None = None
        self._metadata: dict[str, Any] = {
            "verdict": "commented",
            "reason": "",
            "summary": "",
            "suggestions": [],
            "praise": [],
        }

    @property
    def items(self) -> list[dict[str, Any]] | None:
        return self._items

    @property
    def metadata(self) -> dict[str, Any]:
        return self._metadata

    def advance(self, content: str, kind: str) -> None:
        """Record one turn of the stream."""
        self.content += content
        self.kind = kind

        if kind == "complete":
            try:
                parsed = json.loads(self.content)
                self.parsed = parsed
                self._items = parsed.get("items") or parsed.get("findings") or parsed.get("issues")
                self._metadata = {
                    "verdict": parsed.get("verdict", "commented"),
                    "reason": parsed.get("reason", ""),
                    "summary": parsed.get("summary", ""),
                    "suggestions": parsed.get("suggestions", []),
                    "praise": parsed.get("praise", []),
                }
            except json.JSONDecodeError:
                return
