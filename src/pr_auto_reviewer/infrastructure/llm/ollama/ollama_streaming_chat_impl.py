"""Concrete Ollama streaming chat client.

Implements :class:`OllamaStreamingChatABC` using Ollama's
``/api/chat`` streaming endpoint.  The implementation relies on the
engine's GBNF / JSON-schema logit masking (set via the ``format``
parameter) to guarantee valid JSON output, so no prompt‑level
"respond-only-JSON" instructions are needed, and no post-hoc regex
or fence‑stripping is required.

Key invariants
-------------
* ``format: <json_schema>`` is sent with every request — the engine
  masks any token that would violate the schema, making the accumulated
  stream safe to ``json.loads`` on completion.
* The streaming payload follows Ollama's ``/api/chat`` format:
  ``{ "model": ..., "messages": [...], "stream": true, ... }``.
* The final turn always carries ``"kind": "complete"`` with a fully
  parsed JSON object under ``"parsed"``.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any
import httx

from .ollama_streaming_chat_abc import (
    OllamaReviewStream,
    OllamaStreamingChatABC,
)


_REVIEW_JSON_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {
            "type": "string",
            "enum": ["approved", "changes_requested", "commented"],
        },
        "reason": {"type": "string"},
        "summary": {"type": "string"},
        "suggestions": {
            "type": "array",
            "items": {"type": "string"},
        },
        "praise": {
            "type": "array",
            "items": {"type": "string"},
        },
        "items": {
            "type": "array",
            "description": "Per-file findings with severity, description,"
            " and suggested fixes.",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "severity": {
                        "type": "string",
                        "enum": ["critical", "major", "minor", "info"],
                    },
                    "category": {"type": "string"},
                    "description": {"type": "string"},
                    "current_code": {"type": "string"},
                    "suggested_fix": {"type": "string"},
                },
                "required": ["file", "severity", "description"],
            },
        },
    },
    "required": ["verdict", "reason", "summary"],
}


def _format_diff(diff_content: str) -> str:
    """Return the diff wrapped in a minimal code‑block fence.

    Ollama expects the user message to contain the actual content;
    we wrap it so the model treats it as code to review rather than
    conversational text.
    """
    return f"```diff\n{diff_content}\n```"


def _build_review_prompt(diff_content: str, json_schema: dict[str, Any]) -> str:
    """Build the full user message sent to Ollama for a PR review.

    The prompt consists of:
    1. A system instruction asking the model to act as a senior
       code reviewer.
    2. The diff, wrapped in a ```diff ``` block.
    3. The JSON schema — the engine uses this for GBNF logit masking,
       so the model cannot emit fences or stray text.
    """
    schema_block = json.dumps(json_schema, indent=2)

    prompt = f"""You are a senior code reviewer. Analyse the following pull
request diff and produce a structured JSON review. Use the JSON schema
provided — the inference engine will enforce it via GBNF logit masking,
so do NOT wrap your output in markdown fences or add conversational
fluff.

---
{diff_content}

---
JSON schema for the review:
{schema_block}

---
Produce *only* a valid JSON object matching the schema above. The engine
will guarantee validity; do not add any text before or after the JSON.
"""

    return prompt


class OllamaStreamingChatClient(OllamaStreamingChatABC):
    """Ollama streaming chat client using ``/api/chat`` with GBNF schema."""

    def __init__(
        self,
        *,
        model: str,
        host: str,
        timeout: int = 120,
    ) -> None:
        """Initialise the client.

        Parameters
        ----------
        model:
            Name of the Ollama model (e.g. ``"code-review:latest"``).
        host:
            Base URL of the Ollama instance, e.g. ``"http://localhost:11434"``.
        timeout:
            Request timeout in seconds.
        """
        self._model = model
        self._host = host.rstrip("/")
        self._timeout = timeout

    @property
    def model(self) -> str:
        return self._model

    @property
    def host(self) -> str:
        return self._host

    @property
    def json_schema(self) -> dict[str, Any]:
        return _REVIEW_JSON_SCHEMA

    def send_message(
        self,
        message: str,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
        """Send a message to Ollama and return the full accumulated text.

        This is a **blocking** call.  It sends a single ``/api/chat``
        request with ``stream=True`` and ``format: <json_schema>``, then
        collects every ``"message".content`` line until a line with
        ``"done": true`` is received.  The returned string is the raw
        accumulated content; the caller must ``json.loads`` it (the
        engine already guarantees validity thanks to the schema).

        Parameters
        ----------
        message:
            The user message / prompt to send.
        conversation_history:
            Optional previous turns, each as ``{"role": "user"/"assistant",
            "content": "..."}``.  The first element may be a system prompt.

        Returns
        -------
        str
            The complete model response text.
        """
        messages: list[dict[str, Any]] = []

        if conversation_history:
            messages.extend(conversation_history)
        else:
            messages.append(
                {
                    "role": "system",
                    "content": "You are a senior code reviewer. "
                    "Produce valid JSON matching the supplied schema. Do not"
                    " add markdown fences or conversational text.",
                }
            )

        messages.append({"role": "user", "content": message})

        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": True,
            "format": json.dumps(_REVIEW_JSON_SCHEMA),  # GBNF mask
            "options": {"temperature": 0.0, "num_predict": 512},
        }


        url = f"{self._host}/api/chat"
        accumulated_chunks: list[str] = []

        with httpx.Client(timeout=self._timeout) as client, client.stream(
            "POST", url, json=body, headers={"Accept": "application/json"}
        ) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    # Skip malformed lines (should not happen with
                    # schema-enforced output, but be defensive)
                    continue

                # Ollama streams chunks in {"message": {"role": "...",
                # "content": "..."}, "done": bool} format
                msg = data.get("message", {})
                content = msg.get("content", "") or msg.get("thinking", "")
                if content:
                    accumulated_chunks.append(content)
                if data.get("done", False):
                    break

        return "".join(accumulated_chunks).strip()

    async def start_review(
        self,
        repo_path: str,
        pr_number: int,
        diff_content: str,
    ) -> OllamaReviewStream:
        """Stream a full PR review.

        This is an **async generator** that yields ``dict`` turns, each
        with ``"content"``, ``"kind"``, and ``"turn_number"``.  The
        final yielded turn has ``"kind": "complete"`` and includes the
        parsed JSON under ``"parsed"``.

        The method first composes the review prompt (diff + schema),
        then streams the model's response line‑by‑line.  Each line is
        classified into a turn kind based on its content:

        * ``"tool_call"`` — the model asked to read a file, run a
          command, etc. (identified by ``"tool_calls"`` in the response).
        * ``"verdict"`` — the model produced a verdict line (e.g.
          ``"verdict: approved"``) before the final JSON block.
        * ``"unparseable"`` — the accumulated text cannot be decoded as
          JSON (rare, given the schema mask, but we handle it).
        * ``"complete"`` — the final turn with a valid JSON payload.

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
            Each turn dict contains at minimum:
            * ``"content"`` — the raw text / delta from this turn
            * ``"kind"`` — one of ``"tool_call"``, ``"verdict"``,
              ``"unparseable"``, ``"complete"``
            * ``"turn_number"`` — ordinal count (starts at 1)
        """
        review_stream = OllamaReviewStream()

        # Compose the prompt
        prompt = _build_review_prompt(diff_content, self.json_schema)

        # Run the streaming send in a thread pool so we can async‑yield
        # off the main event loop.
        loop = asyncio.get_running_loop()

        accumulated: list[str] = []
        verdict_seen = False

        def _stream_lines() -> None:
            """Synchronous helper that populates ``accumulated``."""
            nonlocal verdict_seen
            import httpx

            body: dict[str, Any] = {
                "model": self._model,
                "messages": [
                    {"role": "user", "content": prompt},
                ],
                "stream": True,
                "format": json.dumps(self.json_schema),
                "options": {"temperature": 0.0, "num_predict": 512},
            }

            url = f"{self._host}/api/chat"
            with httpx.Client(timeout=self._timeout) as client, client.stream(
                "POST", url, json=body, headers={"Accept": "application/json"}
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                        if not line:
                            continue
                        try:
                            data = json.loads(line)
                        except json.JSONDecodeError:
                            continue

                        msg = data.get("message", {})
                        content = msg.get("content", "") or msg.get("thinking", "")
                        done = data.get("done", False)

                        if content:
                            accumulated.append(content)

                        # Classify the turn kind based on the response
                        kind = self._classify_turn(
                            content, data, verdict_seen
                        )
                        review_stream.advance(content, kind)
                        verdict_seen = verdict_seen or (
                            "verdict:" in content.lower()
                            and kind != "tool_call"
                        )

                        if done:
                            break

        # Offload the blocking HTTP I/O to a thread pool
        await loop.run_in_executor(None, _stream_lines)

        # After the stream ends, the final turn should be "complete"
        # with accumulated content that is valid JSON.  Yield any
        # remaining state and return the stream.
        if review_stream.kind != "complete" or not accumulated:
            # Fallback: yield what we have
            review_stream.advance("", "complete")
            review_stream.parsed = {
                "verdict": "commented",
                "reason": "stream ended without complete JSON",
                "summary": "",
                "suggestions": [],
                "items": [],
            }

        # Yield all turns that were collected during the stream.
        # The stream helper already called review_stream.advance() for
        # each line, so we need to re-yield the state.  We reconstruct
        # the turn sequence from the accumulated content.
        # Reset and re-yield from the beginning
        review_stream.turn_number = 1
        review_stream.content = ""
        review_stream.kind = "initial"
        review_stream.parsed = None

        # Re-process accumulated lines into turns
        # (Simplified: just yield a single complete turn with the full
        # accumulated content as the parsed JSON attempt.)
        try:
            parsed = json.loads("".join(accumulated))
        except json.JSONDecodeError:
            parsed = {
                "verdict": "commented",
                "reason": "failed to parse final JSON",
                "summary": "",
                "suggestions": [],
                "items": [],
            }

        review_stream.parsed = parsed
        review_stream._items = parsed.get("items") or parsed.get(
            "findings"
        ) or parsed.get("issues")
        review_stream._metadata = {
            "verdict": parsed.get("verdict", "commented"),
            "reason": parsed.get("reason", ""),
            "summary": parsed.get("summary", ""),
            "suggestions": parsed.get("suggestions", []),
            "praise": parsed.get("praise", []),
        }

        # Yield each intermediate turn we recorded during streaming.
        # For simplicity, yield the final complete turn.
        yield {
            "content": "".join(accumulated),
            "kind": "complete",
            "turn_number": review_stream.turn_number,
            "parsed": review_stream.parsed,
        }

    def _classify_turn(
        self,
        content: str,
        data: dict[str, Any],
        verdict_seen: bool,
    ) -> str:
        """Classify a streaming turn into one of four kinds.

        Parameters
        ----------
        content:
            The text chunk from this streaming line.
        data:
            The parsed JSON line from Ollama's ``/api/chat`` response.
        verdict_seen:
            Whether a verdict line has already been observed in earlier
            turns.

        Returns
        -------
        str
            One of ``"tool_call"``, ``"verdict"``, ``"unparseable"``,
            or ``"complete"``.
        """
        # Check for tool calls — Ollama may include a "tool_calls" key
        # in the response when the model requests file reads, etc.
        tool_calls = data.get("tool_calls")
        if tool_calls:
            return "tool_call"

        content_lower = content.lower().strip()

        # Check for verdict markers before we look for JSON
        if not verdict_seen and (
            content_lower.startswith("verdict:")
            or content_lower in {"approved", "changes requested", "commented"}
        ):
            return "verdict"

        # Try to see if the content is (or leads to) valid JSON.
        # Since the engine enforces the schema, any non-empty accumulation
        # that isn't a tool call or verdict marker should eventually be
        # valid JSON at the end of the stream.
        if content.strip().startswith("{") or content.strip().startswith("["):
            return "complete"

        # Default: continue streaming
        return "unparseable"
