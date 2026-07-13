"""Tests for BackendDetector auto-detection and health-check logic."""

import pytest
import requests as _requests

from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import LlmUnavailableError
from pr_auto_reviewer.infrastructure.llm.backend_detector import BackendDetector


def _make_fake_get(code: int):
    """Return a fake requests.get that responds with *code*."""

    def _get(url, timeout=None, **kwargs):
        _ = timeout, kwargs  # unused but must accept

        class FakeResponse:
            status_code = code
            reason = "Mocked"
            text = ""

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise _requests.HTTPError(f"Mocked {self.status_code}")

        return FakeResponse()

    return _get


def _make_connection_error():
    """Return a fake requests.get that raises ConnectionError."""

    def _get(url, timeout=None, **kwargs):
        raise _requests.ConnectionError("Connection refused")

    return _get


class TestBackendDetector:
    """Tests for BackendDetector.detect()."""

    def test_detect_llama_cpp_available(self, monkeypatch):
        """llama.cpp /v1/models returns 200 — detected first, no Ollama probe."""
        monkeypatch.setattr(_requests, "get", _make_fake_get(200))

        result = BackendDetector("http://localhost:8080").detect()

        assert result == "llama_cpp"

    def test_detect_ollama_fallback(self, monkeypatch):
        """llama.cpp probe fails, /api/tags returns 200 — falls back to Ollama."""
        call_count = 0

        def _get(url, timeout=None, **kwargs):
            nonlocal call_count
            call_count += 1

            class FakeResponse:
                status_code = 200
                reason = "Mocked"
                text = ""

                def raise_for_status(self):
                    pass

            if call_count == 1:
                raise _requests.ConnectionError("llama.cpp is down")
            return FakeResponse()

        monkeypatch.setattr(_requests, "get", _get)

        result = BackendDetector("http://localhost:11434").detect()

        assert result == "ollama"

    def test_detect_neither_raises(self, monkeypatch):
        """Both endpoints return non-200 — raises LlmUnavailableError."""
        monkeypatch.setattr(_requests, "get", _make_fake_get(503))

        with pytest.raises(LlmUnavailableError) as exc_info:
            BackendDetector("http://localhost:9999").detect()

        assert "No LLM backend found" in str(exc_info.value)
        assert "/v1/models" in str(exc_info.value)
        assert "/api/tags" in str(exc_info.value)

    def test_detect_llama_cpp_non_200_falls_back(self, monkeypatch):
        """/v1/models returns 500, /api/tags returns 200 — returns Ollama."""
        call_count = 0

        def _get(url, timeout=None, **kwargs):
            nonlocal call_count
            call_count += 1

            class FakeResponse:
                status_code = 500 if call_count == 1 else 200
                reason = "Mocked"
                text = ""

                def raise_for_status(self):
                    if self.status_code >= 400:
                        raise _requests.HTTPError(f"Mocked {self.status_code}")

            return FakeResponse()

        monkeypatch.setattr(_requests, "get", _get)

        result = BackendDetector("http://localhost:11434").detect()

        assert result == "ollama"

    def test_detect_connection_error_falls_back(self, monkeypatch):
        """/v1/models throws ConnectionError, /api/tags returns 200."""
        call_count = 0

        def _get(url, timeout=None, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise _requests.ConnectionError("Connection refused")

            class FakeResponse:
                status_code = 200
                reason = "Mocked"
                text = ""

                def raise_for_status(self):
                    pass

            return FakeResponse()

        monkeypatch.setattr(_requests, "get", _get)

        result = BackendDetector("http://localhost:11434").detect()

        assert result == "ollama"

    def test_detect_llama_cpp_first_wins(self, monkeypatch):
        """Both endpoints return 200 — llama.cpp wins (first match)."""
        monkeypatch.setattr(_requests, "get", _make_fake_get(200))

        result = BackendDetector("http://localhost:8080").detect()

        assert result == "llama_cpp"

    def test_host_trailing_slash_stripped(self, monkeypatch):
        """Host with trailing slash — probes without double slash."""
        captured_urls = []

        def _get(url, timeout=None, **kwargs):
            captured_urls.append(url)

            class FakeResponse:
                status_code = 200
                reason = "Mocked"
                text = ""

                def raise_for_status(self):
                    pass

            return FakeResponse()

        monkeypatch.setattr(_requests, "get", _get)

        BackendDetector("http://localhost:8080/").detect()

        assert captured_urls[0] == "http://localhost:8080/v1/models"


class TestHealthCheck:
    """Tests for BackendDetector.health_check()."""

    def test_healthy_llama_cpp(self, monkeypatch):
        """/v1/models returns 200 — no exception raised."""
        monkeypatch.setattr(_requests, "get", _make_fake_get(200))

        BackendDetector("http://localhost:8080").health_check("llama_cpp")

    def test_healthy_ollama(self, monkeypatch):
        """/api/tags returns 200 — no exception raised."""
        monkeypatch.setattr(_requests, "get", _make_fake_get(200))

        BackendDetector("http://localhost:11434").health_check("ollama")

    def test_unhealthy_llama_cpp_raises(self, monkeypatch):
        """/v1/models returns 503 — raises LlmUnavailableError."""
        monkeypatch.setattr(_requests, "get", _make_fake_get(503))

        with pytest.raises(LlmUnavailableError) as exc_info:
            BackendDetector("http://localhost:8080").health_check("llama_cpp")

        assert "llama_cpp" in str(exc_info.value)
        assert "/v1/models" in str(exc_info.value)

    def test_unhealthy_ollama_raises(self, monkeypatch):
        """/api/tags returns 500 — raises LlmUnavailableError."""
        monkeypatch.setattr(_requests, "get", _make_fake_get(500))

        with pytest.raises(LlmUnavailableError) as exc_info:
            BackendDetector("http://localhost:11434").health_check("ollama")

        assert "ollama" in str(exc_info.value)
        assert "/api/tags" in str(exc_info.value)

    def test_connection_error_raises(self, monkeypatch):
        """ConnectionError — raises LlmUnavailableError."""
        monkeypatch.setattr(_requests, "get", _make_connection_error())

        with pytest.raises(LlmUnavailableError):
            BackendDetector("http://localhost:8080").health_check("llama_cpp")

    def test_unknown_backend_raises_value_error(self):
        """Unknown backend string — raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            BackendDetector("http://localhost:11434").health_check("openai")

        assert "openai" in str(exc_info.value)
