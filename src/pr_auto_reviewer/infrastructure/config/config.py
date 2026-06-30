"""Application configuration — loads and validates settings from environment.

Environment variables are sourced from config files via python-dotenv,
then read through ``os.environ`` to build a single ``Config`` dataclass
consumed by the dependency-injection container.

Search order (highest priority last, so it wins):
  - Production: ``~/.config/pr-auto-reviewer/config``, then repo ``.env``
  - Development: repo ``.env``, then ``~/.config/pr-auto-reviewer/config``
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from pr_auto_reviewer.infrastructure.llm.prompt_mode import PromptMode
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider


@dataclass
class Config:
    env: str
    platform_token: str
    platform_mode: GitProvider = GitProvider.CODEBERG
    platform_api_url: str = "https://codeberg.org/api/v1"
    reviewer_token: str | None = None
    reviewer_username: str | None = None
    # Added for 'both' mode
    github_token: str | None = None
    github_reviewer_token: str | None = None
    github_reviewer_username: str | None = None
    github_review_mode: str = "formal"
    codeberg_token: str | None = None
    codeberg_reviewer_token: str | None = None
    codeberg_reviewer_username: str | None = None

    llm_host: str = "http://localhost:11434"
    llm_model: str | None = None
    poll_interval: int = 60
    debug: bool = False
    output_mode: str = "codeberg"
    output_dest: str = "stdout"
    fragments_dir: str = "fragments"
    max_prompt_tokens: int = 9999
    max_file_chars: int = 3000
    max_files: int = 10
    max_structure_lines: int = 100
    use_compact_template: bool = False
    prompt_mode: PromptMode = PromptMode.MONOLITHIC
    use_strict_fragment_selection: bool = False


def _get_repo_root() -> Path:
    return Path(__file__).parent.parent.parent.parent.parent


def _is_installed() -> bool:
    return not (_get_repo_root() / ".env").exists()


def _normalize_platform_api_url(url: str, platform_mode: GitProvider) -> str:
    if platform_mode == GitProvider.CODEBERG:
        if not url.endswith("/api/v1"):
            return url + "/api/v1"
    return url


def load_config() -> Config:
    repo_root = Path(__file__).parent.parent.parent.parent.parent
    env = os.environ.get("ENV", "").strip()

    if not env:
        env = "production" if _is_installed() else "development"

    user_config_path = os.path.expanduser("~/.config/pr-auto-reviewer/config")
    repo_env_path = repo_root / ".env"

    if env == "production":
        paths = [repo_env_path, user_config_path]
    else:
        paths = [user_config_path, repo_env_path]

    for path in paths:
        if os.path.exists(path):
            load_dotenv(path, override=True)

    platform_mode_raw = (
        os.environ.get("PLATFORM_MODE") or os.environ.get("FORGEJO_MODE") or "forgejo"
    ).strip()
    platform_mode = GitProvider.parse(platform_mode_raw)

    # Set default API URL based on platform mode
    default_api_url = (
        "https://api.github.com"
        if platform_mode == GitProvider.GITHUB
        else "https://codeberg.org"
    )

    _raw_api_url = os.environ.get("PLATFORM_API_URL")
    if not _raw_api_url:
        if platform_mode == GitProvider.CODEBERG:
            _raw_api_url = os.environ.get("FORGEJO_HOST") or default_api_url
        elif platform_mode == GitProvider.GITHUB:
            _raw_api_url = default_api_url
        else:
            _raw_api_url = default_api_url

    platform_api_url = _normalize_platform_api_url(_raw_api_url.strip(), platform_mode)

    # Base tokens
    if platform_mode == GitProvider.GITHUB:
        platform_token = (
            os.environ.get("PLATFORM_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
        ).strip()
        reviewer_token = (
            os.environ.get("REVIEWER_TOKEN")
            or os.environ.get("GITHUB_REVIEWER_TOKEN")
            or ""
        ).strip() or None
        reviewer_username = (
            os.environ.get("REVIEWER_USERNAME")
            or os.environ.get("GITHUB_REVIEWER_USERNAME")
            or ""
        ).strip() or None
        # Fallback: if owner token is missing, try using the reviewer token for read-only access
        if not platform_token:
            platform_token = reviewer_token or ""
    else:
        platform_token = (
            os.environ.get("PLATFORM_TOKEN") or os.environ.get("FORGEJO_TOKEN") or ""
        ).strip()
        reviewer_token = (
            os.environ.get("REVIEWER_TOKEN")
            or os.environ.get("FORGEJO_REVIEWER_TOKEN")
            or ""
        ).strip() or None
        reviewer_username = (
            os.environ.get("REVIEWER_USERNAME")
            or os.environ.get("FORGEJO_REVIEWER_USERNAME")
            or ""
        ).strip() or None
        # Fallback: if owner token is missing, try using the reviewer token
        if not platform_token:
            platform_token = reviewer_token or ""

    # Platform-specific tokens for BOTH mode
    github_token = os.environ.get("GITHUB_TOKEN", "").strip() or None
    github_reviewer_token = os.environ.get("GITHUB_REVIEWER_TOKEN", "").strip() or None
    github_reviewer_username = (
        os.environ.get("GITHUB_REVIEWER_USERNAME", "").strip() or None
    )
    github_review_mode = os.environ.get("GITHUB_REVIEW_MODE", "formal").strip()

    codeberg_token = os.environ.get("FORGEJO_TOKEN", "").strip() or None
    codeberg_reviewer_token = (
        os.environ.get("FORGEJO_REVIEWER_TOKEN", "").strip() or None
    )
    codeberg_reviewer_username = (
        os.environ.get("FORGEJO_REVIEWER_USERNAME", "").strip() or None
    )

    llm_host = (
        os.environ.get("LLM_HOST")
        or os.environ.get("OLLAMA_HOST")
        or "http://localhost:11434"
    ).strip()
    llm_model = (
        os.environ.get("LLM_MODEL") or os.environ.get("OLLAMA_MODEL") or ""
    ).strip() or None

    output_mode = os.environ.get("REVIEW_OUTPUT", "codeberg").strip()
    output_dest = os.environ.get("REVIEW_OUTPUT_DEST", "stdout").strip()
    max_prompt_tokens = int(os.environ.get("MAX_PROMPT_TOKENS", "9999"))
    max_file_chars = int(os.environ.get("MAX_FILE_CHARS", "3000"))
    max_files = int(os.environ.get("MAX_FILES", "10"))
    max_structure_lines = int(os.environ.get("MAX_STRUCTURE_LINES", "100"))
    use_compact_template = (
        os.environ.get("USE_COMPACT_TEMPLATE", "false").lower() == "true"
    )
    prompt_mode = PromptMode.parse(os.environ.get("PROMPT_MODE", ""))

    use_strict_fragment_selection = (
        os.environ.get("USE_STRICT_FRAGMENT_SELECTION", "false").lower() == "true"
    )

    return Config(
        env=env,
        platform_token=platform_token,
        platform_mode=platform_mode,
        platform_api_url=platform_api_url,
        reviewer_token=reviewer_token,
        reviewer_username=reviewer_username,
        github_token=github_token,
        github_reviewer_token=github_reviewer_token,
        github_reviewer_username=github_reviewer_username,
        github_review_mode=github_review_mode,
        codeberg_token=codeberg_token,
        codeberg_reviewer_token=codeberg_reviewer_token,
        codeberg_reviewer_username=codeberg_reviewer_username,
        llm_host=llm_host,
        llm_model=llm_model,
        poll_interval=int(os.environ.get("POLL_INTERVAL", "60")),
        debug=os.environ.get("DEBUG", "0") == "1",
        output_mode=output_mode,
        output_dest=output_dest,
        max_prompt_tokens=max_prompt_tokens,
        max_file_chars=max_file_chars,
        max_files=max_files,
        max_structure_lines=max_structure_lines,
        use_compact_template=use_compact_template,
        prompt_mode=prompt_mode,
        use_strict_fragment_selection=use_strict_fragment_selection,
    )
