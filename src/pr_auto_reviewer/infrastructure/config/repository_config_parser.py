"""Parse repository selection configuration."""

from __future__ import annotations

from pathlib import Path

from pr_auto_reviewer.domain.value_objects.clone_protocol import CloneProtocol
from pr_auto_reviewer.infrastructure.config.repository_settings import RepositorySettings


class RepositoryConfigParser:
    """Build repository selection and clone settings from environment values."""

    def parse(self, source: dict[str, str]) -> RepositorySettings:
        """Parse clone protocol, repository filters, and forced pull requests."""
        raw_allow_list = source.get("REPOS_ALLOW_LIST", "")
        raw_force_pr = source.get("FORCE_PR", "").strip()
        return RepositorySettings(
            clone_protocol=CloneProtocol.parse(source.get("CLONE_PROTOCOL", "https")),
            local_clone_base_dir=source.get(
                "LOCAL_CLONE_BASE_DIR",
                str(Path("~/.cache/pr-auto-reviewer/repos").expanduser()),
            ).strip(),
            repos_filter=source.get("REPOS_FILTER", "").strip(),
            repos_allow_list=tuple(
                item.strip()
                for item in raw_allow_list.replace("\n", ",").split(",")
                if item.strip()
            ),
            force_pr=int(raw_force_pr) if raw_force_pr else None,
        )
