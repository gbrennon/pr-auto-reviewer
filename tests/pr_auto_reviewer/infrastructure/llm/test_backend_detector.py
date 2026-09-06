"""Tests for BackendDetector."""

from __future__ import annotations

from typing import Any

import pytest
import requests

from pr_auto_reviewer.domain.exceptions.llm_unavailable_error import (
    LlmUnavailableError,
)
from pr_auto_reviewer.infrastructure.llm.backend_detector import (
    BackendDetector,
)


class _FakeProbeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class TestBackendDetector:
    def test_detect_prefers_llama_cpp_when_available(self) -> None:
        def fake_get(url: str, **_kwargs: Any) -> _FakeProbeResponse:
            if "/v1/models" in url:
                return _FakeProbeResponse(200)
            return _FakeProbeResponse(404)

        detector = BackendDetector(http_get=fake_get)
        assert detector.detect() == "llama_cpp"

    def test_detect_selects_ollama_when_only_ollama_responds(self) -> None:
        def fake_get(url: str, **_kwargs: Any) -> _FakeProbeResponse:
            if "/api/tags" in url:
                return _FakeProbeResponse(200)
            return _FakeProbeResponse(404)

        detector = BackendDetector(http_get=fake_get)
        assert detector.detect() == "ollama"

    def test_detect_defaults_to_ollama_when_neither_responds(self) -> None:
        def fake_get(_url: str, **_kwargs: Any) -> Any:
            raise requests.ConnectionError("Offline")

        detector = BackendDetector(http_get=fake_get)
        assert detector.detect() == "ollama"

    def test_health_check_llama_cpp_success_and_failure(self) -> None:
        def fake_get_ok(url: str, **_kwargs: Any) -> _FakeProbeResponse:
            if "/v1/models" in url:
                return _FakeProbeResponse(200)
            return _FakeProbeResponse(500)

        detector_ok = BackendDetector(http_get=fake_get_ok)
        detector_ok.health_check("llama_cpp")

        def fake_get_fail(_url: str, **_kwargs: Any) -> Any:
            raise requests.ConnectionError("Down")

        detector_fail = BackendDetector(http_get=fake_get_fail)
        with pytest.raises(LlmUnavailableError):
            detector_fail.health_check("llama_cpp")

    def test_health_check_ollama_success_and_failure(self) -> None:
        def fake_get_ok(url: str, **_kwargs: Any) -> _FakeProbeResponse:
            if "/api/tags" in url:
                return _FakeProbeResponse(200)
            return _FakeProbeResponse(500)

        detector_ok = BackendDetector(http_get=fake_get_ok)
        detector_ok.health_check("ollama")

        def fake_get_fail(_url: str, **_kwargs: Any) -> Any:
            raise requests.ConnectionError("Down")

        detector_fail = BackendDetector(http_get=fake_get_fail)
        with pytest.raises(LlmUnavailableError):
            detector_fail.health_check("ollama")

    def test_health_check_unknown_backend_raises_value_error(self) -> None:
        detector = BackendDetector()
        with pytest.raises(ValueError):
            detector.health_check("unsupported_backend")
