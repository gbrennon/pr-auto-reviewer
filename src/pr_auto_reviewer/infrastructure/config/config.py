"""Configuration module for PR Auto Reviewer."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class Config:
    """Configuration settings for the PR Auto Reviewer."""

    env: str
    forgejo_token: str
    forgejo_mode: str = "codeberg"
    forgejo_host: str = "https://codeberg.org/api/v1"
    forgejo_reviewer_token: Optional[str] = None
    forgejo_reviewer_username: Optional[str] = None
    ollama_host: str = "http://localhost:11434"
    ollama_model: Optional[str] = None
    poll_interval: int = 60
    debug: bool = False


def _get_repo_root() -> Path:
    """Get the repository root path."""
    return Path(__file__).parent.parent.parent.parent


def _is_installed() -> bool:
    """Detect if running from an installed package (not development)."""
    return not (_get_repo_root() / ".env").exists()


def _normalize_forgejo_host(url: str) -> str:
    """Ensure the Forgejo/Codeberg host URL includes /api/v1 suffix."""
    url = url.rstrip("/")
    # GitHub uses a different API path structure
    if "github.com" in url or url == "https://api.github.com":
        return "https://api.github.com"
    # Forgejo/Codeberg needs /api/v1 suffix
    if not url.endswith("/api/v1"):
        return url + "/api/v1"
    return url


def load_config() -> Config:
    """Load configuration from environment variables.

    Priority based on mode:
    - development (default, .env exists): .env first, then user config
    - production (installed, no .env): user config first, then .env

    Later files override earlier ones.

    Returns:
        Config: The loaded configuration.

    Raises:
        RuntimeError: If required configuration is missing.
    """
    repo_root = Path(__file__).parent.parent.parent.parent
    env = os.environ.get("ENV", "").strip()

    if not env:
        env = "production" if _is_installed() else "development"

    user_config_path = os.path.expanduser("~/.config/pr-auto-reviewer/config")
    repo_env_path = repo_root / ".env"

    if env == "production":
        paths = [user_config_path, repo_env_path]
    else:
        paths = [repo_env_path, user_config_path]

    for path in paths:
        if os.path.exists(path):
            load_dotenv(path, override=True)

    forgejo_token = os.environ.get("FORGEJO_TOKEN", "").strip()
    if not forgejo_token:
        raise RuntimeError("FORGEJO_TOKEN is required")

    return Config(
        env=env,
        forgejo_token=forgejo_token,
        forgejo_mode=os.environ.get("FORGEJO_MODE", "codeberg").strip(),
        forgejo_host=_normalize_forgejo_host(
            os.environ.get("FORGEJO_HOST", "https://codeberg.org/api/v1").strip()
        ),
        forgejo_reviewer_token=os.environ.get("FORGEJO_REVIEWER_TOKEN", "").strip() or None,
        forgejo_reviewer_username=os.environ.get("FORGEJO_REVIEWER_USERNAME", "").strip() or None,
        ollama_host=os.environ.get("OLLAMA_HOST", "http://localhost:11434").strip(),
        ollama_model=os.environ.get("OLLAMA_MODEL", "").strip() or None,
        poll_interval=int(os.environ.get("POLL_INTERVAL", "60")),
        debug=os.environ.get("DEBUG", "0") == "1",
    )