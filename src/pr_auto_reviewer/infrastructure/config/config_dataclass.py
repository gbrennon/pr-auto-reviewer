"""Config dataclass — all application configuration in one place."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from pr_auto_reviewer.domain.value_objects.clone_protocol import CloneProtocol
from pr_auto_reviewer.infrastructure.config.advisor_granularity import (
    AdvisorGranularity,
)
from pr_auto_reviewer.infrastructure.config.org_token_overrides import (
    OrgTokenOverrides,
)
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider


@dataclass
class Config:
    env: str
    platform_mode: GitProvider = GitProvider.FORGEJO
    clone_protocol: CloneProtocol = CloneProtocol.HTTPS

    github_api_url: str = "https://api.github.com"
    forgejo_api_url: str = "https://codeberg.org/api/v1"

    github_owner_token: str = ""
    github_reviewer_token: str = ""
    github_reviewer_username: str = ""
    github_review_mode: str = "formal"

    forgejo_owner_token: str = ""
    forgejo_reviewer_token: str = ""
    forgejo_reviewer_username: str = ""

    org_token_overrides: OrgTokenOverrides = field(default_factory=OrgTokenOverrides)

    llm_backend: str = "ollama"
    llm_host: str = "http://localhost:11434"
    llm_model: str | None = None
    llm_timeout: int = 120
    llm_max_retries: int = 5
    llm_max_turns: int = 10
    advisor_max_blocks: int = 2
    review_max_conversations: int = 48
    review_max_tries: int = 2
    llm_call_budget: int = 300
    advisor_granularity: AdvisorGranularity = AdvisorGranularity.PHASE
    poll_interval: int = 60
    run_once: bool = False
    repos_filter: str = ""
    repos_allow_list: tuple[str, ...] = ()
    force_pr: int | None = None
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
    local_clone_base_dir: str = str(Path("~/.cache/pr-auto-reviewer/repos").expanduser())
