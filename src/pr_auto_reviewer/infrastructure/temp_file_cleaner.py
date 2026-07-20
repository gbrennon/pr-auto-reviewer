"""TempFileCleaner — remove stale debug/diagnostic files from temporary storage.

Transient files cleaned by this module:
- ``/tmp/http-*.log``          — HTTP client debug logs
- ``/tmp/ollama-prompt-*.txt`` — LLM prompt debug dumps
- ``/tmp/ollama_raw_response.txt`` — LLM raw response dump

Persisted state that MUST NOT be touched:
- ``/tmp/pr-auto-reviewer/rate-limits/`` — rate-limit tracking state

None of the glob patterns above match the rate-limits directory, so
no explicit exclusion is needed.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

_CLEANUP_PATTERNS: tuple[str, ...] = (
    "http-*.log",
    "ollama-prompt-*.txt",
    "ollama_raw_response.txt",
)


def clean_temp_files(
    max_age_seconds: int = 3600,
    target_dir: Path | None = None,
) -> int:
    """Delete matching temp files older than *max_age_seconds*.

    Args:
        max_age_seconds: Files with age exceeding this are deleted.
        target_dir: Directory to scan; defaults to ``/tmp``.

    Returns:
        Count of files deleted.
    """
    if target_dir is None:
        target_dir = Path("/tmp")

    now = time.time()
    deleted = 0

    for pattern in _CLEANUP_PATTERNS:
        for candidate in target_dir.glob(pattern):
            try:
                age = now - candidate.stat().st_mtime
            except OSError:
                logger.debug("Could not stat %s, skipping", candidate)
                continue

            if age <= max_age_seconds:
                continue

            try:
                candidate.unlink()
                deleted += 1
                logger.debug("Removed stale temp file: %s", candidate)
            except OSError:
                logger.warning(
                    "Failed to remove %s, skipping",
                    candidate,
                    exc_info=True,
                )

    if deleted:
        logger.info("Cleaned up %d stale temp file(s)", deleted)
    else:
        logger.debug("No stale temp files to clean")

    return deleted
