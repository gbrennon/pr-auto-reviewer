"""Tests for GitPlatformHttpClient using fixture data."""

from __future__ import annotations

import logging
from typing import Any

import pytest
import requests as requests_lib

from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)


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
            raise requests_lib.exceptions.HTTPError(response=self)


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
            raise requests_lib.exceptions.HTTPError(
                response=_FakeResponse(status_code=422, text='{"error": "gone"}', content=b'{"error": "gone"}')
            )

        monkeypatch.setattr(requests_lib, "post", fake_post)
        client = GitPlatformHttpClient("https://x", "t")
        with pytest.raises(requests_lib.exceptions.HTTPError):
            client.post("/test", {"k": "v"})
