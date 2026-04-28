"""Configuration module for PR Auto Reviewer."""

import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class Config:
    """Configuration settings for the PR Auto Reviewer."""

    forgejo_token: str
    forgejo_mode: str = "codeberg"
    forgejo_host: str = "https://codeberg.org"
    forgejo_reviewer_token: Optional[str] = None
    forgejo_reviewer_username: Optional[str] = None
    ollama_host: str = "http://localhost:11434"
    ollama_model: Optional[str] = None
    poll_interval: int = 60
    debug: bool = False

def load_config() -> Config:
    """Load configuration from environment variables or config file.

    Returns:
        Config: The loaded configuration.

    Raises:
        RuntimeError: If required configuration is missing.
    """
    config_path = os.path.expanduser("~/.config/pr-auto-reviewer/config")
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    env_path = os.path.join(repo_root, ".env")

    # Try to load from user config first
    if os.path.exists(config_path):
        load_env_file(config_path)
        return _create_config()

    # Try to load from repo .env
    if os.path.exists(env_path):
        load_env_file(env_path)
        return _create_config()

    raise RuntimeError(
        "No config found. Either:\n"
        "  - Install: bash scripts/install-service.sh\n"
        "  - Manual: cp .env.example .env and edit"
    )

def load_env_file(file_path: str) -> None:
    """Load environment variables from a file.

    Args:
        file_path: Path to the environment file.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#"):
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

def _create_config() -> Config:
    """Create Config object from environment variables.

    Returns:
        Config: The configuration object.

    Raises:
        RuntimeError: If required configuration is missing.
    """
    forgejo_token = os.environ.get("FORGEJO_TOKEN", "").strip()
    if not forgejo_token:
        raise RuntimeError("FORGEJO_TOKEN is required")

    return Config(
        forgejo_token=forgejo_token,
        forgejo_mode=os.environ.get("FORGEJO_MODE", "codeberg").strip(),
        forgejo_host=os.environ.get("FORGEJO_HOST", "https://codeberg.org").strip(),
        forgejo_reviewer_token=os.environ.get("FORGEJO_REVIEWER_TOKEN", "").strip() or None,
        forgejo_reviewer_username=os.environ.get("FORGEJO_REVIEWER_USERNAME", "").strip() or None,
        ollama_host=os.environ.get("OLLAMA_HOST", "http://localhost:11434").strip(),
        ollama_model=os.environ.get("OLLAMA_MODEL", "").strip() or None,
        poll_interval=int(os.environ.get("POLL_INTERVAL", "60")),
        debug=os.environ.get("DEBUG", "0") == "1",
    )