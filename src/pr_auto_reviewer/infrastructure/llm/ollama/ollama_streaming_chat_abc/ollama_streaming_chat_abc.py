from ._shared import *


class OllamaStreamingChatABC(ABC):
    """Abstract base for Ollama streaming chat integration.

    Subclasses must implement the low-level HTTP streaming call and
    provide a schema‑aware parser that relies on the underlying engine's
    GBNF logit masking rather than prompt‑level instructions.
    """

    @property
    @abstractmethod
    def model(self) -> str:
        """Name of the Ollama model in use."""

    @property
    @abstractmethod
    def host(self) -> str:
        """Base URL of the Ollama instance (e.g. ``http://localhost:11434``)."""

    @property
    @abstractmethod
    def json_schema(self) -> dict[str, Any]:
        """JSON‑Schema object passed as the ``format`` parameter to Ollama.

        When supplied, the underlying inference engine masks invalid tokens
        during sampling, guaranteeing that the model cannot emit markdown
        fences, conversational fluff, or malformed JSON.
        """

    @abstractmethod
    def send_message(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
        """Send *message* to Ollama and stream the full accumulated response.

        Parameters
        ----------
        message:
            The user message to send.
        conversation_history:
            Optional previous turns, each as a ``{role, content}`` dict.
            The first element may be a system prompt.

        Returns
        -------
        str
            The complete model response text (accumulated across all
            streaming lines).  The caller is responsible for parsing it
            (e.g. ``json.loads``) — the engine already guarantees valid
            JSON when ``json_schema`` is set.
        """

    @abstractmethod
    async def start_review(
        self,
        repo_path: str,
        pr_number: int,
        diff_content: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream a full PR review across multiple LLM turns.

        Parameters
        ----------
        repo_path:
            Path to the local git repository clone.
        pr_number:
            The pull/merge request number.
        diff_content:
            The raw diff text for the PR.

        Yields
        ------
        dict[str, Any]
            Each yielded dict represents one turn and contains at least
            the following keys:
            * ``"content"`` — the delta / raw text from this turn
            * ``"kind"`` — one of ``"tool_call"``, ``"verdict"``,
              ``"unparseable"``, or ``"complete"``
            * ``"turn_number"`` — ordinal turn count (starting at 1)

        The stream must complete with a final yield kind ``"complete"``
        that includes the fully‑accumulated, fully‑validated JSON object
        under the key ``"parsed"``.
        """
        yield {}

    def parse_streaming_response(
        self, raw_lines: list[str], model: str
    ) -> tuple[list[dict[str, Any]] | None, dict[str, Any]]:
        """Parse a list of raw streaming lines into items and metadata.

        The default implementation accumulates lines, performs a single
        ``json.loads`` at the end (relying on the ``format`` schema), and
        extracts ``verdict``, ``reason``, ``summary``, ``items``, etc.

        Subclasses may override if they need per‑line parsing (e.g. for
        tool‑call detection mid‑stream).

        Parameters
        ----------
        raw_lines:
            The ``"message"."content"`` delta from each streaming line,
            as returned by ``response.iter_lines()``.
        model:
            The Ollama model name, for logging / error messages.

        Returns
        -------
        (items, metadata) : tuple
            * ``items`` — ``list`` of item dicts (``file``, ``severity``,
              ``category``, ``description``, ``current_code``,
              ``suggested_fix``) or ``None`` if no structured items were
              found.
            * ``metadata`` — ``dict`` with keys ``"verdict"``,
              ``"reason``, ``"summary``, ``"suggestions``, ``"praise``.
        """
        accumulated = "".join(raw_lines)
        try:
            data = json.loads(accumulated)
        except json.JSONDecodeError:
            return None, {
                "verdict": "commented",
                "reason": "failed to decode JSON from accumulated stream",
                "summary": "",
                "suggestions": [],
                "praise": [],
            }

        items: list[dict[str, Any]] | None = None
        items_raw = data.get("items") or data.get("findings") or data.get("issues")
        if isinstance(items_raw, list):
            items = [
                {
                    "file": item.get("file", ""),
                    "severity": item.get("severity", "info"),
                    "category": item.get("category", "maintainability"),
                    "description": item.get("description", ""),
                    "line": item.get("line", ""),
                    "current_code": item.get("current_code", ""),
                    "suggested_fix": item.get("suggested_fix", ""),
                }
                for item in items_raw
                if isinstance(item, dict)
            ]

        metadata: dict[str, Any] = {
            "verdict": data.get("verdict", "commented"),
            "reason": data.get("reason", ""),
            "summary": data.get("summary", ""),
            "suggestions": data.get("suggestions", []),
            "praise": data.get("praise", []),
        }

        return items, metadata

