"""AgentConversationService — run a multi-turn agentic conversation with tool access."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)
_MAX_REPEATED_TOOL_CALLS = 3
_MAX_READ_FILE_REPLAYS = 2
_MIN_READ_FILE_REPLAY_FILES = 2


@dataclass(frozen=True)
class _FinalVerdictContext:
    phase_name: str
    repo_path: Path
    changed_files: list[str]
    review_session: str
    model: str
    readable_changed_files: tuple[str, ...]
    readable_coverage_files: tuple[str, ...]
    read_file_paths: set[str]
    read_file_count: int
    run_snippet_count: int
    existing_item_ids: frozenset[str]
    accumulated_praise: list[dict[str, Any]]
    accumulated_suggestions: list[dict[str, Any]]

