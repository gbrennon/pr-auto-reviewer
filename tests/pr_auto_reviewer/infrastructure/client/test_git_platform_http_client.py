"""Tests for GitPlatformHttpClient using fixture data."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pytest
import requests as requests_lib

from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)

from pr_auto_reviewer.infrastructure.client.remote_host_backoff import (
    RemoteHostBackoff,
)


class _Clock:
    def __init__(self) -> None:
        self.value = 100.0
        self.sleeps: list[float] = []

    def now(self) -> float:
        return self.value

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.value += seconds




class _FakeResponse:
    """Reusable fake requests.Response for monkeypatch injection."""


    def __init__(self, *, status_code: int = 200, json_data: Any = None, text: str = "", content: bytes = b"") -> None:
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.content = content

    def json(self) -> Any:
        if self._json_data is not None:
            return self._json_data
        return {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise requests_lib.exceptions.HTTPError()


class TestGitPlatformHttpClient:
    """Tests for GitPlatformHttpClient using captured fixture data."""

    def test_get_returns_dict(self, patched_client):
        """GET returns JSON dict with PR data."""
        result = patched_client.get("/repos/owner/repo/pulls/1")
        assert "number" in result

    def test_get_raw_returns_diff(self, patched_client):
        """GET_RAW returns diff text."""
        text = patched_client.get_raw("/repos/owner/repo/pulls/1.diff")
        assert isinstance(text, str)
        assert text.startswith("diff --git")

    def test_base_url_property(self, patched_client):
        """base_url property returns expected value."""
        assert patched_client.base_url == "https://codeberg.org/api/v1"

    def test_base_url_strips_trailing_slash(self):
        """__init__ strips trailing slash from base_url."""
        client = GitPlatformHttpClient("https://codeberg.org/api/v1/", "t")
        assert client.base_url == "https://codeberg.org/api/v1"

    def test_post(self, monkeypatch):
        """POST sends JSON body and returns response dict."""
        monkeypatch.setattr(
            requests_lib, "post",
            lambda *a, **kw: _FakeResponse(status_code=201, json_data={"id": 999}),
        )
        client = GitPlatformHttpClient("https://x", "t")
        result = client.post("/repos/test/pulls/1/comments", {"body": "hello"})
        assert result["id"] == 999

    def test_get_with_params(self, monkeypatch):
        """GET passes query params."""
        monkeypatch.setattr(
            requests_lib, "get",
            lambda *a, **kw: _FakeResponse(json_data={"data": [{"login": "gbrennon"}]}),
        )
        client = GitPlatformHttpClient("https://x", "t")
        result = client.get("/users/search", q="gbrennon", limit=1)
        assert isinstance(result, dict)

    def test_get_raw_returns_text(self, monkeypatch):
        """GET_RAW returns the response text content."""
        monkeypatch.setattr(
            requests_lib, "get",
            lambda *a, **kw: _FakeResponse(text="diff --git a/file.py b/file.py\n+new line\n"),
        )
        client = GitPlatformHttpClient("https://x", "t")
        result = client.get_raw("/repos/test/pulls/1.diff")
        assert isinstance(result, str)
        assert result.startswith("diff --git")

    def test_get_does_not_log_response_body(self, monkeypatch, caplog):
        """GET does not emit response bodies into debug logs."""
        monkeypatch.setattr(
            requests_lib,
            "get",
            lambda *a, **kw: _FakeResponse(
                json_data={"ok": True},
                text='[{"full_name": "owner/private-repository"}]',
                content=b"payload",
            ),
        )
        caplog.set_level(logging.DEBUG, logger="pr_auto_reviewer.infrastructure.client.git_platform_http_client")
        client = GitPlatformHttpClient("https://x", "t")

        client.get("/user/repos")

        assert "owner/private-repository" not in caplog.text
        assert "body (" not in caplog.text

    def test_get_raw_uses_auth_header(self, monkeypatch):
        """GET_RAW passes Authorization header correctly."""
        captured_kwargs: dict[str, Any] = {}

        def fake_get(url: str, **kwargs: Any) -> _FakeResponse:
            captured_kwargs.update(kwargs)
            return _FakeResponse(text="ok")

        monkeypatch.setattr(requests_lib, "get", fake_get)
        client = GitPlatformHttpClient("https://x", "t")
        client.get_raw("/repos/test/pulls/1.diff")
        assert "headers" in captured_kwargs
        assert captured_kwargs["headers"]["Authorization"] == "token t"

    def test_github_auth_header_is_bearer(self):
        """GitHub mode uses Bearer authorization."""
        client = GitPlatformHttpClient("https://api.github.com", "ghp_xxx", "github")
        assert client._get_auth_header() == {"Authorization": "Bearer ghp_xxx"}

    def test_codeberg_auth_header_is_token(self):
        """Codeberg mode uses 'token' prefix."""
        client = GitPlatformHttpClient("https://codeberg.org/api/v1", "tok", "forgejo")
        assert client._get_auth_header() == {"Authorization": "token tok"}

    def test_get_merges_custom_headers(self, monkeypatch):
        """get() merges custom headers with auth header."""
        captured_headers: dict[str, str] = {}

        def fake_get(url: str, *, headers: dict[str, str], params: Any, timeout: int) -> _FakeResponse:
            captured_headers.update(headers)
            return _FakeResponse(json_data={"ok": True})

        monkeypatch.setattr(requests_lib, "get", fake_get)
        client = GitPlatformHttpClient("https://x", "t")
        result = client.get("/test", headers={"X-Custom": "v"})
        assert result == {"ok": True}
        assert captured_headers["X-Custom"] == "v"
        assert "Authorization" in captured_headers

    def test_get_raw_merges_custom_headers(self, monkeypatch):
        """get_raw() merges custom headers with auth header."""
        captured_headers: dict[str, str] = {}

        def fake_get(url: str, *, headers: dict[str, str], timeout: int) -> _FakeResponse:
            captured_headers.update(headers)
            return _FakeResponse(text="raw")

        monkeypatch.setattr(requests_lib, "get", fake_get)
        client = GitPlatformHttpClient("https://x", "t")
        result = client.get_raw("/test", headers={"X-Custom": "v"})
        assert result == "raw"
        assert captured_headers["X-Custom"] == "v"
        assert "Authorization" in captured_headers

    def test_post_logs_http_error(self, monkeypatch, caplog):
        """post() logs response body on HTTPError."""
        caplog.set_level(logging.ERROR)

        def fake_post(url: str, *, headers: Any, json: Any, timeout: int) -> _FakeResponse:
            raise requests_lib.exceptions.HTTPError()

        monkeypatch.setattr(requests_lib, "post", fake_post)
        client = GitPlatformHttpClient("https://x", "t")
        with pytest.raises(requests_lib.exceptions.HTTPError):
            client.post("/test", {"k": "v"})

    def test_default_verified_cache_path_when_not_provided_then_uses_app_paths_cache_dir(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        """Verify default verified cache path resolves to AppPaths.cache_dir() / 'verified-tokens.json'."""
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))

        client = GitPlatformHttpClient("https://codeberg.org/api/v1", "t")

        assert client._verified_cache_path == tmp_path / "pr-auto-reviewer" / "verified-tokens.json"

    def test_retryable_failures_wait_before_fourth_request(self, monkeypatch) -> None:
        clock = _Clock()
        backoff = RemoteHostBackoff(
            threshold=4, clock=clock.now, sleeper=clock.sleep,
        )
        attempts = 0

        def fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
            nonlocal attempts
            attempts += 1
            if attempts <= 3:
                raise requests_lib.ConnectionError("connection refused")
            return _FakeResponse(json_data={"ok": True})

        monkeypatch.setattr(requests_lib, "get", fake_get)
        client = GitPlatformHttpClient(
            "https://codeberg.org/api/v1",
            "token",
            remote_host_backoff=backoff,
        )

        for _ in range(3):
            with pytest.raises(requests_lib.ConnectionError):
                client.get("/user")

        client.get("/user")

        assert clock.sleeps == [60.0, 120.0, 180.0]

    def test_manager_and_reviewer_clients_share_backoff(self, monkeypatch) -> None:
        clock = _Clock()
        backoff = RemoteHostBackoff(
            threshold=4, clock=clock.now, sleeper=clock.sleep,
        )
        attempts = 0

        def fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
            nonlocal attempts
            attempts += 1
            if attempts <= 3:
                raise requests_lib.ConnectionError("connection refused")
            return _FakeResponse(json_data={"ok": True})

        monkeypatch.setattr(requests_lib, "get", fake_get)
        manager = GitPlatformHttpClient(
            "https://codeberg.org/api/v1",
            "manager-token",
            client_label="manager",
            remote_host_backoff=backoff,
        )
        reviewer = GitPlatformHttpClient(
            "https://codeberg.org/api/v1",
            "reviewer-token",
            client_label="reviewer",
            remote_host_backoff=backoff,
        )

        for client in (manager, reviewer, manager):
            with pytest.raises(requests_lib.ConnectionError):
                client.get("/user")

        reviewer.get("/user")

        assert clock.sleeps == [60.0, 120.0, 180.0]

    @pytest.mark.parametrize("status_code", [400, 401, 403, 404, 422])
    def test_non_transient_http_errors_do_not_trigger_backoff(
        self, monkeypatch, status_code: int,
    ) -> None:
        clock = _Clock()
        backoff = RemoteHostBackoff(clock=clock.now, sleeper=clock.sleep)
        responses = [_FakeResponse(status_code=status_code), _FakeResponse()]

        def fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
            return responses.pop(0)

        monkeypatch.setattr(requests_lib, "get", fake_get)
        client = GitPlatformHttpClient(
            "https://codeberg.org/api/v1",
            "token",
            remote_host_backoff=backoff,
        )

        with pytest.raises(requests_lib.HTTPError):
            client.get("/user")
        client.get("/user")

        assert clock.sleeps == []

    def test_non_retryable_response_resets_mixed_retryable_streak(
        self, monkeypatch,
    ) -> None:
        clock = _Clock()
        backoff = RemoteHostBackoff(clock=clock.now, sleeper=clock.sleep)
        responses = [
            _FakeResponse(status_code=500),
            _FakeResponse(status_code=500),
            _FakeResponse(status_code=401),
            _FakeResponse(status_code=500),
            _FakeResponse(status_code=200, json_data={"ok": True}),
        ]

        def fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
            return responses.pop(0)

        monkeypatch.setattr(requests_lib, "get", fake_get)
        client = GitPlatformHttpClient(
            "https://codeberg.org/api/v1",
            "token",
            remote_host_backoff=backoff,
        )

        for _ in range(2):
            with pytest.raises(requests_lib.HTTPError):
                client.get("/user")
        with pytest.raises(requests_lib.HTTPError):
            client.get("/user")
        with pytest.raises(requests_lib.HTTPError):
            client.get("/user")
        client.get("/user")

        assert clock.sleeps == [60.0, 120.0, 60.0]

    @pytest.mark.parametrize("status_code", [429, 500])
    def test_retryable_http_errors_count_toward_backoff(
        self, monkeypatch, status_code: int,
    ) -> None:
        clock = _Clock()
        backoff = RemoteHostBackoff(
            threshold=4, clock=clock.now, sleeper=clock.sleep,
        )
        responses = [_FakeResponse(status_code=status_code) for _ in range(3)]
        responses.append(_FakeResponse())

        def fake_get(*args: Any, **kwargs: Any) -> _FakeResponse:
            return responses.pop(0)

        monkeypatch.setattr(requests_lib, "get", fake_get)
        client = GitPlatformHttpClient(
            "https://codeberg.org/api/v1",
            "token",
            remote_host_backoff=backoff,
        )

        for _ in range(3):
            with pytest.raises(requests_lib.HTTPError):
                client.get("/user")
        client.get("/user")

        assert clock.sleeps == [60.0, 120.0, 180.0]
