"""Ollama streaming chat abstract contract.

Defines the interface for streaming conversations with Ollama's
``/api/chat`` endpoint. Concrete adapters implement this to provide
engine-level GBNF/json-schema enforced output, eliminating the need
for prompt-time "respond-only-JSON" instructions or post-hoc regex
stripping."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any

__all__ = ['ABC', 'Any', 'AsyncIterator', 'abstractmethod', 'annotations', 'json']
