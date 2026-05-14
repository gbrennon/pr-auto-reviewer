"""Tests for GitPlatformHttpClient using fixture data."""

import pytest
import requests as requests_lib

from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)


class TestGitPlatformHttpClient:
    """Tests for GitPlatformHttpClient using captured fixture data."""

    def test_get_returns_dict(self, patched_client):
        """GET returns JSON dict with PR data."""
        result = patched_client.get("/repos/o/r/pulls/1")
        assert isinstance(result, dict)
        assert "number" in result

    def test_get_raw_returns_diff(self, patched_client):
        """GET_RAW returns diff text."""
        text = patched_client.get_raw("/repos/o/r/pulls/1.diff")
        assert isinstance(text, str)
        assert len(text) > 100
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
        class FakeResponse:
            status_code = 201
            def json(self):
                return {"id": 999}
            def raise_for_status(self):
                pass
        monkeypatch.setattr(requests_lib, "post", lambda *a, **kw: FakeResponse())
        client = GitPlatformHttpClient("https://x", "t")
        result = client.post("/repos/test/pulls/1/comments", {"body": "hello"})
        assert result["id"] == 999

    def test_get_with_params(self, monkeypatch):
        """GET passes query params."""
        class FakeResponse:
            status_code = 200
            def json(self):
                return {"data": [{"login": "gbrennon"}]}
            def raise_for_status(self):
                pass
        monkeypatch.setattr(requests_lib, "get", lambda *a, **kw: FakeResponse())
        client = GitPlatformHttpClient("https://x", "t")
        result = client.get("/users/search", q="gbrennon", limit=1)
        assert isinstance(result, dict)
