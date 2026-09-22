"""Parse source-control platform configuration."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.config.forgejo_api_url_normalizer import ForgejoApiUrlNormalizer
from pr_auto_reviewer.infrastructure.config.platform_settings import PlatformSettings
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider


class PlatformConfigParser:
    """Build platform settings from environment values."""

    def parse(self, source: dict[str, str]) -> PlatformSettings:
        """Parse platform endpoints, credentials, and review mode."""
        mode = source.get("PLATFORM_MODE", source.get("FORGEJO_MODE", "forgejo"))
        forgejo_url = source.get("FORGEJO_API_URL", source.get("FORGEJO_HOST", "https://codeberg.org"))
        return PlatformSettings(
            mode=GitProvider.parse(mode.strip()),
            github_api_url=source.get("GITHUB_API_URL", "https://api.github.com").strip(),
            forgejo_api_url=ForgejoApiUrlNormalizer.normalize(forgejo_url.strip()),
            github_owner_token=source.get("GITHUB_OWNER_TOKEN", "").strip(),
            github_reviewer_token=source.get("GITHUB_REVIEWER_TOKEN", "").strip(),
            github_reviewer_username=source.get("GITHUB_REVIEWER_USERNAME", "").strip(),
            github_review_mode=source.get("GITHUB_REVIEW_MODE", "formal").strip(),
            forgejo_owner_token=source.get("FORGEJO_OWNER_TOKEN", "").strip(),
            forgejo_reviewer_token=source.get("FORGEJO_REVIEWER_TOKEN", "").strip(),
            forgejo_reviewer_username=source.get("FORGEJO_REVIEWER_USERNAME", "").strip(),
        )
