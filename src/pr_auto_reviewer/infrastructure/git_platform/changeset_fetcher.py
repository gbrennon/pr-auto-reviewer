"""GitChangesetFetcherAdapter — wraps GitPlatformHttpClient to implement ChangesetFetcherPort."""

from __future__ import annotations

import logging
import re

from pr_auto_reviewer.application.ports.outbound.changeset_fetcher_port import (
    ChangesetFetcherPort,
)
from pr_auto_reviewer.domain.exceptions.empty_diff_error import EmptyDiffError
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.infrastructure.client.git_platform_http_client import (
    GitPlatformHttpClient,
)

logger = logging.getLogger(__name__)

# Regex to extract changed file paths from unified-diff headers.
_DIFF_FILE_PATH_RE = re.compile(
    r"^diff --git a/(.+?) b/(.+?)$", re.MULTILINE
)


class GitChangesetFetcherAdapter(ChangesetFetcherPort):
    """Fetches a pull-request diff and the full content of each changed file."""

    def __init__(self, client: GitPlatformHttpClient) -> None:
        self._client = client

    # ------------------------------------------------------------------ [port]
    def fetch(self, pr_id: PullRequestId, sha: CommitSha) -> PullRequestDiff:
        """Return the diff and per-file contents for *pr_id* at *sha*."""
        # -- [http] fetch unified diff ---------------------------------------
        diff_path = f"/repos/{pr_id.repository}/pulls/{pr_id.number}.diff"
        raw_diff = self._client.get_raw(diff_path)

        # -- [err] empty / tiny diff -----------------------------------------
        if not raw_diff or len(raw_diff.strip()) < 50:
            raise EmptyDiffError(
                f"Diff for {pr_id} at {sha} is empty or too short"
            )

        # -- [map] extract changed file paths from diff headers --------------
        file_paths: set[str] = set()
        for match in _DIFF_FILE_PATH_RE.finditer(raw_diff):
            # b-side path is the "new" file (may be /dev/null for deletions)
            new_path = match.group(2)
            if new_path and new_path != "/dev/null":
                file_paths.add(new_path)

        # -- [http] fetch each file's content (skip deleted / unreadable) ---
        file_contents: dict[str, str] = {}
        for file_path in sorted(file_paths):
            raw_path = f"/repos/{pr_id.repository}/raw/{sha.value}/{file_path}"
            try:
                content = self._client.get_raw(raw_path)
                file_contents[file_path] = content
            except Exception:
                # 404 or other errors → file was probably deleted; skip silently.
                logger.debug("Skipping unreadable file: %s", file_path)

        # -- [map] build domain value-object ---------------------------------
        return PullRequestDiff(
            pr_id=pr_id,
            head_sha=sha,
            diff_content=raw_diff,
            file_contents=file_contents,
        )
