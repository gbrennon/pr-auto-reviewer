from __future__ import annotations

GITHUB_DIFF_MEDIA = "application/vnd.github.v3.diff"
GITHUB_RAW_MEDIA = "application/vnd.github.v3.raw"

from pr_auto_reviewer.infrastructure.client.git_platform_http_client import GitPlatformHttpClient
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider

__all__ = [
    "GITHUB_DIFF_MEDIA",
    "GITHUB_RAW_MEDIA",
]
