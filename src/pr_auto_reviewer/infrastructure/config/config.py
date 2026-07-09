import logging
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

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


def _get_repo_root() -> Path:
    return Path(__file__).parent.parent.parent.parent.parent


def _is_installed() -> bool:
    return not (_get_repo_root() / ".env").exists()


def _normalize_forgejo_api_url(url: str) -> str:
    if url.endswith("/api/v1"):
        return url
    return url.rstrip("/") + "/api/v1"


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
        if (path if isinstance(path, Path) else Path(path)).exists():
            load_dotenv(path, override=True)

    platform_mode_raw = (
        os.environ.get("PLATFORM_MODE") or os.environ.get("FORGEJO_MODE") or "forgejo"
    ).strip()
    platform_mode = GitProvider.parse(platform_mode_raw)

    github_api_url = (
        os.environ.get("GITHUB_API_URL", "").strip() or "https://api.github.com"
    )
    forgejo_api_url = (
        os.environ.get("FORGEJO_API_URL", "").strip()
        or os.environ.get("FORGEJO_HOST", "").strip()
        or "https://codeberg.org"
    )
    forgejo_api_url = _normalize_forgejo_api_url(forgejo_api_url)

    github_owner_token = os.environ.get("GITHUB_OWNER_TOKEN", "").strip()
    github_reviewer_token = os.environ.get("GITHUB_REVIEWER_TOKEN", "").strip()
    github_reviewer_username = os.environ.get("GITHUB_REVIEWER_USERNAME", "").strip()
    github_review_mode = os.environ.get("GITHUB_REVIEW_MODE", "formal").strip()

    forgejo_owner_token = os.environ.get("FORGEJO_OWNER_TOKEN", "").strip()
    forgejo_reviewer_token = os.environ.get("FORGEJO_REVIEWER_TOKEN", "").strip()
    forgejo_reviewer_username = os.environ.get("FORGEJO_REVIEWER_USERNAME", "").strip()

    llm_host = (
        os.environ.get("LLM_HOST")
        or os.environ.get("OLLAMA_HOST")
        or "http://localhost:11434"
    ).strip()
    llm_model = (
        os.environ.get("LLM_MODEL") or os.environ.get("OLLAMA_MODEL") or ""
    ).strip() or None

    output_mode = os.environ.get("REVIEW_OUTPUT", "").strip()
    output_path: str | None = None
    if output_mode.startswith("file:"):
        output_path = output_mode.removeprefix("file:") or None
        output_mode = "terminal"
    elif not output_mode:
        output_mode = "forgejo"

    poll_interval = int(os.environ.get("POLL_INTERVAL", "60"))
    debug = os.environ.get("DEBUG", "0").strip() in ("1", "true", "yes")
    max_prompt_tokens = int(os.environ.get("MAX_PROMPT_TOKENS", "9999"))
    max_file_chars = int(os.environ.get("MAX_FILE_CHARS", "3000"))
    max_files = int(os.environ.get("MAX_FILES", "10"))
    max_structure_lines = int(os.environ.get("MAX_STRUCTURE_LINES", "100"))
    use_compact_template = (
        os.environ.get("USE_COMPACT_TEMPLATE", "false").lower() == "true"
    )
    use_strict_fragment_selection = (
        os.environ.get("USE_STRICT_FRAGMENT_SELECTION", "false").lower() == "true"
    )

    return Config(
        env=env,
        platform_mode=platform_mode,
        github_api_url=github_api_url,
        forgejo_api_url=forgejo_api_url,
        github_owner_token=github_owner_token,
        github_reviewer_token=github_reviewer_token,
        github_reviewer_username=github_reviewer_username,
        github_review_mode=github_review_mode,
        forgejo_owner_token=forgejo_owner_token,
        forgejo_reviewer_token=forgejo_reviewer_token,
        forgejo_reviewer_username=forgejo_reviewer_username,
        llm_host=llm_host,
        llm_model=llm_model,
        poll_interval=poll_interval,
        debug=debug,
        output_mode=output_mode,
        output_path=output_path,
        max_prompt_tokens=max_prompt_tokens,
        max_file_chars=max_file_chars,
        max_files=max_files,
        max_structure_lines=max_structure_lines,
        use_compact_template=use_compact_template,
        use_strict_fragment_selection=use_strict_fragment_selection,
    )
