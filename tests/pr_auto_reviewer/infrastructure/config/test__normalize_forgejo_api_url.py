"""Tests for ForgejoApiUrlNormalizer."""

from pr_auto_reviewer.infrastructure.config.forgejo_api_url_normalizer import (
    ForgejoApiUrlNormalizer,
)


class TestForgejoApiUrlNormalizer:
    def test_normalize_preserves_url_with_api_v1_suffix(self):
        assert (
            ForgejoApiUrlNormalizer.normalize("https://codeberg.org/api/v1")
            == "https://codeberg.org/api/v1"
        )

    def test_normalize_appends_api_v1_to_plain_host(self):
        assert (
            ForgejoApiUrlNormalizer.normalize("https://codeberg.org")
            == "https://codeberg.org/api/v1"
        )

    def test_normalize_appends_api_v1_removing_trailing_slash(self):
        assert (
            ForgejoApiUrlNormalizer.normalize("https://codeberg.org/")
            == "https://codeberg.org/api/v1"
        )
