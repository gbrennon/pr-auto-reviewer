"""Config dataclass — all application configuration in one place."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider


@dataclass
class Config:
    env: str
    platform_mode: GitProvider = GitProvider.FORGEJO

    github_api_url: str = "https://api.github.com"
    forgejo_api_url: str = "https://codeberg.org/api/v1"

    github_owner_token: str = ""
    github_reviewer_token: str = ""
    github_reviewer_username: str = ""
    github_review_mode: str = "formal"

    forgejo_owner_token: str = ""
    forgejo_reviewer_token: str = ""
    forgejo_reviewer_username: str = ""

    llm_host: str = "http://localhost:11434"
    llm_model: str | None = None
    poll_interval: int = 60
    debug: bool = False
    output_mode: str = "forgejo"
    output_path: str | None = None
    fragments_dir: str = ""
    max_prompt_tokens: int = 9999
    max_file_chars: int = 3000
    max_files: int = 10
    max_structure_lines: int = 100
    use_compact_template: bool = False
    use_strict_fragment_selection: bool = False