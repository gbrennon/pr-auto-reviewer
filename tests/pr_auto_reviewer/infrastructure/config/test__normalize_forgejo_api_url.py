"""Tests for _normalize_forgejo_api_url helper."""

from pr_auto_reviewer.infrastructure.config.config import _normalize_forgejo_api_url


class TestNormalizeForgejoApiUrl:
    def test_preserves_url_with_api_v1_suffix(self):
        assert (
            _normalize_forgejo_api_url("https://codeberg.org/api/v1")
            == "https://codeberg.org/api/v1"
        )

    def test_appends_api_v1_to_plain_host(self):
        assert (
            _normalize_forgejo_api_url("https://codeberg.org")
            == "https://codeberg.org/api/v1"
        )

    def test_appends_api_v1_removing_trailing_slash(self):
        assert (
            _normalize_forgejo_api_url("https://codeberg.org/")
            == "https://codeberg.org/api/v1"
        )
