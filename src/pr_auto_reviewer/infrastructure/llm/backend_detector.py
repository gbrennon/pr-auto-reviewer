"""LLM backend auto-detection via HTTP health probes."""

import logging

import requests

from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError

logger = logging.getLogger(__name__)


class BackendDetector:
    """Detects and health-checks LLM backends at a given host."""

    _DEFAULT_TIMEOUT = 2  # seconds — fast fail for unresponsive backends

    _ENDPOINTS: dict[str, str] = {
        "llama_cpp": "/v1/models",
        "ollama": "/api/tags",
    }

    def __init__(self, host: str, timeout: int | None = None) -> None:
        self._host = host.rstrip("/")
        self._timeout = timeout if timeout is not None else self._DEFAULT_TIMEOUT

    def detect(self) -> str:
        """Probe the host to determine which LLM backend is available.

        Tries llama.cpp first (GET /v1/models), then Ollama (GET /api/tags).
        Returns ``"llama_cpp"`` or ``"ollama"``.
        Raises :exc:`LlmUnavailableError` if neither endpoint responds.
        """
        logger.info("Auto-detecting LLM backend at %s ...", self._host)

        # llama.cpp: OpenAI-compatible /v1/models
        try:
            resp = requests.get(
                f"{self._host}/v1/models", timeout=self._timeout
            )
            if resp.status_code == 200:
                logger.info("Detected llama.cpp backend")
                return "llama_cpp"
        except requests.RequestException:
            logger.debug("llama.cpp probe failed", exc_info=True)

        # Ollama: /api/tags
        try:
            resp = requests.get(
                f"{self._host}/api/tags", timeout=self._timeout
            )
            if resp.status_code == 200:
                logger.info("Detected Ollama backend")
                return "ollama"
        except requests.RequestException:
            logger.debug("Ollama probe failed", exc_info=True)

        raise LlmUnavailableError(
            f"No LLM backend found at {self._host}. "
            "Tried llama.cpp (/v1/models) and Ollama (/api/tags). "
            "Check LLM_API or start a local LLM server."
        )

    def health_check(self, backend: str) -> None:
        """Verify *backend* is reachable and responding.

        Raises :exc:`LlmUnavailableError` if the health check fails.
        Raises :exc:`ValueError` if *backend* is unknown.
        """
        endpoint = self._ENDPOINTS.get(backend)
        if endpoint is None:
            raise ValueError(
                f"Unknown LLM backend: {backend!r}. "
                "Expected 'ollama' or 'llama_cpp'."
            )

        logger.info("Health-checking %s backend at %s ...", backend, self._host)
        try:
            resp = requests.get(
                f"{self._host}{endpoint}", timeout=self._timeout
            )
            resp.raise_for_status()
            logger.info("%s backend is healthy", backend)
        except requests.RequestException as exc:
            logger.error(
                "%s backend at %s is unreachable: %s", backend, self._host, exc
            )
            raise LlmUnavailableError(
                f"LLM backend '{backend}' is not reachable at "
                f"{self._host}{endpoint}. Error: {exc}. "
                "Check LLM_API or start a local LLM server."
            ) from exc
