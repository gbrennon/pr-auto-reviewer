"""Parsed source-control platform configuration."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider


@dataclass(frozen=True)
class PlatformSettings:
    """Configuration for GitHub and Forgejo integrations."""

    mode: GitProvider
    github_api_url: str
    forgejo_api_url: str
    github_owner_token: str
    github_reviewer_token: str
    github_reviewer_username: str
    github_review_mode: str
    forgejo_owner_token: str
    forgejo_reviewer_token: str
    forgejo_reviewer_username: str
