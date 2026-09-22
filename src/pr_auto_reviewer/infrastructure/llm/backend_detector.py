"""BackendDetector — probe and detect active LLM backend services."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import requests

from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)

logger = logging.getLogger(__name__)


class BackendDetector:
    """Probes endpoints to detect active LLM backends and verify connectivity."""

    def __init__(
        self,
        ollama_host: str = "http://localhost:11434",
        llama_cpp_host: str = "http://localhost:8080",
        timeout: float = 3.0,
        http_get: Callable[..., Any] | None = None,
    ) -> None:
        """Initialize detector with endpoint host targets and timeout."""
        self._ollama_host = self._normalize_host(
            ollama_host or "http://localhost:11434"
        )
        self._llama_cpp_host = self._normalize_host(
            llama_cpp_host or "http://localhost:8080"
        )
        self._timeout = timeout
        self._http_get = http_get

    @staticmethod
    def _normalize_host(host: str) -> str:
        """Ensure host URL starts with an HTTP scheme and has no trailing slashes."""
        cleaned = host.strip().rstrip("/")
        if not cleaned.startswith(("http://", "https://")):
            cleaned = f"http://{cleaned}"
        if cleaned.endswith("/v1"):
            return cleaned[:-3]
        return cleaned

    def detect(self) -> str:
        """Detect available LLM backend, preferring llama.cpp over Ollama."""
        if self._probe(f"{self._llama_cpp_host}/v1/models"):
            logger.info(
                "Detected llama.cpp backend at %s", self._llama_cpp_host
            )
            return "llama_cpp"
        if self._probe(f"{self._ollama_host}/api/tags"):
            logger.info("Detected Ollama backend at %s", self._ollama_host)
            return "ollama"
        logger.info(
            "No active backend detected; defaulting to Ollama at %s",
            self._ollama_host,
        )
        return "ollama"

    def health_check(self, backend: str) -> None:
        """Verify that the specified backend is reachable."""
        if backend == "llama_cpp":
            self._health_check_llama_cpp()
            return
        if backend == "ollama":
            self._health_check_ollama()
            return
        raise ValueError(f"Unknown LLM backend: {backend}")

    def _probe(self, url: str) -> bool:
        """Send a GET request to a health or models endpoint."""
        get_fn = self._http_get or requests.get
        try:
            response = get_fn(url, timeout=self._timeout)
            return bool(response.status_code == 200)
        except requests.RequestException:
            return False

    def _health_check_llama_cpp(self) -> None:
        """Verify connectivity to llama.cpp models endpoint."""
        if not self._probe(f"{self._llama_cpp_host}/v1/models"):
            raise LlmUnavailableError(
                f"llama.cpp is unreachable at {self._llama_cpp_host}"
            )

    def _health_check_ollama(self) -> None:
        """Verify connectivity to Ollama tags endpoint."""
        if not self._probe(f"{self._ollama_host}/api/tags"):
            raise LlmUnavailableError(
                f"Ollama is unreachable at {self._ollama_host}"
            )
