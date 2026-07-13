"""Fixtures for Config — captured from real .env files."""

from __future__ import annotations

from pathlib import Path


class ConfigFixtures:
    """Sample .env content captured from real configurations."""

    # Minimal .env for forgejo-only setup
    forgejo_minimal: str = """PLATFORM_MODE=forgejo
FORGEJO_API_URL=https://codeberg.org/api/v1
FORGEJO_OWNER_TOKEN=fj_token_abc123
"""

    # .env with GitHub settings
    github_settings: str = """PLATFORM_MODE=github
GITHUB_API_URL=https://github.example.com
GITHUB_OWNER_TOKEN=gh_token_xyz
GITHUB_REVIEWER_TOKEN=gh_reviewer_xyz
GITHUB_REVIEWER_USERNAME=review-bot
GITHUB_REVIEW_MODE=informal
"""

    # .env with numeric overrides
    numeric_overrides: str = """PLATFORM_MODE=forgejo
POLL_INTERVAL=30
MAX_PROMPT_TOKENS=4096
MAX_FILE_CHARS=2000
MAX_FILES=5
MAX_STRUCTURE_LINES=50
"""

    # .env with boolean flags
    boolean_flags: str = """PLATFORM_MODE=forgejo
DEBUG=1
USE_COMPACT_TEMPLATE=true
USE_STRICT_FRAGMENT_SELECTION=true
"""

    # .env with file output mode
    file_output: str = """PLATFORM_MODE=forgejo
REVIEW_OUTPUT=file:/tmp/review.md
"""

    # .env with file output but no path
    file_output_no_path: str = """PLATFORM_MODE=forgejo
REVIEW_OUTPUT=file:
"""

    # .env with LLM settings
    llm_settings: str = """PLATFORM_MODE=forgejo
LLM_API=http://llm:8080
LLM_MODEL=gpt-4
"""

    # .env with LLM settings (ollama)
    ollama_settings: str = """PLATFORM_MODE=forgejo
LLM_API=http://ollama:11434
LLM_MODEL=code-review:latest
"""

    # .env with FORGEJO_HOST fallback (no FORGEJO_API_URL)
    forgejo_host_fallback: str = """PLATFORM_MODE=forgejo
FORGEJO_HOST=https://git.example.com
FORGEJO_OWNER_TOKEN=fj_owner
FORGEJO_REVIEWER_TOKEN=fj_reviewer
FORGEJO_REVIEWER_USERNAME=fj_bot
"""

    # .env with FORGEJO_MODE fallback (no PLATFORM_MODE)
    forgejo_mode_fallback: str = """FORGEJO_MODE=forgejo
"""

    # .env with explicit ENV=staging
    explicit_env: str = """ENV=staging
PLATFORM_MODE=forgejo
"""

    @staticmethod
    def write_env_file(dir_path: Path, content: str) -> Path:
        """Write *content* to a .env file in *dir_path* and return the path."""
        env_path = dir_path / ".env"
        env_path.write_text(content)
        return env_path
