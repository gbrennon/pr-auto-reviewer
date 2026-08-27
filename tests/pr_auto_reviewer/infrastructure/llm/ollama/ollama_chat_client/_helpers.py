"""Shared helpers, fixtures, and imports for the split test modules."""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any

import pytest
import requests

from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.domain.exceptions.review_budget_exhausted_error import (
    ReviewBudgetExhaustedError,
)
from pr_auto_reviewer.domain.value_objects.conversation_message import (
    ConversationMessage,
)
from pr_auto_reviewer.infrastructure.llm.ollama.ollama_chat_client import (
    OllamaChatClient,
)


def _json_line(message: dict[str, Any]) -> bytes:
    return json.dumps(
        {"message": message}, ensure_ascii=False
    ).encode("utf-8")


__all__ = ['Any', 'ConversationMessage', 'Iterator', 'LlmUnavailableError', 'OllamaChatClient', 'ReviewBudgetExhaustedError', '_FakeStreamingResponse', '_json_line', 'annotations', 'json', 'pytest', 'requests']


class _FakeStreamingResponse:
    """Fake ``requests.Response`` mirroring requests' decode-then-split.

    ``iter_lines(decode_unicode=True)`` decodes the raw body using
    ``self.encoding`` (ISO-8859-1 when unset, like requests) and then
    splits on line boundaries — faithfully reproducing the NEL-split
    corruption that used to break ``json.loads``.
    """

    def __init__(self, raw_body: bytes, *, status_code: int = 200) -> None:
        self._raw_body = raw_body
        self.status_code = status_code
        self.encoding: str | None = None

    def raise_for_status(self) -> None:
        pass

    def iter_lines(self, decode_unicode: bool) -> Iterator[str]:
        text = self._raw_body.decode(self.encoding or "iso-8859-1")
        for line in text.splitlines():
            if line:
                yield line
