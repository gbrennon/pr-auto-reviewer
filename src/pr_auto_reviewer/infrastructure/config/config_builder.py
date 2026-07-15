"""Builds a Config from a flat key-value dict."""

from __future__ import annotations

from pr_auto_reviewer.infrastructure.config.config_dataclass import Config
from pr_auto_reviewer.infrastructure.config.forgejo_api_url_normalizer import (
    ForgejoApiUrlNormalizer,
)
from pr_auto_reviewer.infrastructure.git_platform.git_provider import GitProvider


class ConfigBuilder:
    """Builds a ``Config`` from a flat ``{KEY: value}`` dict.

    Args:
        source: Dict with config keys (e.g. from ``dotenv_values`` or
            ``os.environ``).
        env_name: Value for ``Config.env``.
    """

    def build(self, source: dict[str, str], env_name: str) -> Config:
        platform_mode_raw = (
            self._get(source, "PLATFORM_MODE")
            or self._get(source, "FORGEJO_MODE")
            or "forgejo"
        )
        platform_mode = GitProvider.parse(platform_mode_raw)

        github_api_url = self._get(source, "GITHUB_API_URL") or "https://api.github.com"
        forgejo_api_url = (
            self._get(source, "FORGEJO_API_URL")
            or self._get(source, "FORGEJO_HOST")
            or "https://codeberg.org"
        )
        forgejo_api_url = ForgejoApiUrlNormalizer.normalize(forgejo_api_url)

        github_owner_token = self._get(source, "GITHUB_OWNER_TOKEN")
        github_reviewer_token = self._get(source, "GITHUB_REVIEWER_TOKEN")
        github_reviewer_username = self._get(source, "GITHUB_REVIEWER_USERNAME")
        github_review_mode = self._get(source, "GITHUB_REVIEW_MODE") or "formal"

        forgejo_owner_token = self._get(source, "FORGEJO_OWNER_TOKEN")
        forgejo_reviewer_token = self._get(source, "FORGEJO_REVIEWER_TOKEN")
        forgejo_reviewer_username = self._get(source, "FORGEJO_REVIEWER_USERNAME")

        llm_host = (
            self._get(source, "LLM_HOST")
            or self._get(source, "OLLAMA_HOST")
            or "http://localhost:11434"
        )
        llm_model = (
            self._get(source, "LLM_MODEL") or self._get(source, "OLLAMA_MODEL")
        ) or None

        output_mode = self._get(source, "REVIEW_OUTPUT")
        output_path: str | None = None
        if output_mode.startswith("file:"):
            output_path = output_mode.removeprefix("file:") or None
            output_mode = "terminal"
        elif not output_mode:
            output_mode = "forgejo"

        poll_interval = int(source.get("POLL_INTERVAL") or "60")
        debug = self._get(source, "DEBUG") in ("1", "true", "yes")
        max_prompt_tokens = int(source.get("MAX_PROMPT_TOKENS") or "9999")
        max_file_chars = int(source.get("MAX_FILE_CHARS") or "3000")
        max_files = int(source.get("MAX_FILES") or "10")
        max_structure_lines = int(source.get("MAX_STRUCTURE_LINES") or "100")
        use_compact_template = (
            self._get(source, "USE_COMPACT_TEMPLATE").lower() == "true"
        )
        use_strict_fragment_selection = (
            self._get(source, "USE_STRICT_FRAGMENT_SELECTION").lower() == "true"
        )

        return Config(
            env=env_name,
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

    @classmethod
    def _get(cls, source: dict[str, str], key: str, default: str = "") -> str:
        return source.get(key, default).strip()