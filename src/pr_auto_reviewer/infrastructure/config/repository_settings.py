"""Parsed repository selection and clone configuration."""

from __future__ import annotations

from dataclasses import dataclass

from pr_auto_reviewer.domain.value_objects.clone_protocol import CloneProtocol


@dataclass(frozen=True)
class RepositorySettings:
    """Configuration controlling repository selection and local clones."""

    clone_protocol: CloneProtocol
    local_clone_base_dir: str
    repos_filter: str
    repos_allow_list: tuple[str, ...]
    force_pr: int | None
