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

_DIFF_FILE_PATH_RE = re.compile(
    r"^\s*diff --git a/(.+?)\s+b/(.+?)$", re.MULTILINE
)


class GithubChangesetFetcher(ChangesetFetcherPort):
    def __init__(self, client: GitPlatformHttpClient) -> None:
        self._client = client

    def _fetch_commit_messages(self, pr_id: PullRequestId) -> list[str]:
        commits_path = f"/repos/{pr_id.repository}/pulls/{pr_id.number}/commits"
        try:
            data = self._client.get(commits_path, limit=30, repo=pr_id.repository)
            commits = data if isinstance(data, list) else data.get("data", [])
            messages: list[str] = []
            for c in commits:
                msg = (c.get("commit", {}).get("message", "")).strip()
                if msg:
                    subject = msg.split("\n\n")[0].split("\n")[0].strip()
                    messages.append(subject)
            logger.debug("Fetched %d commit messages for %s", len(messages), pr_id)
            return messages
        except Exception:
            logger.debug("Could not fetch commits for %s", pr_id)
            return []

    def fetch(self, pr_id: PullRequestId, sha: CommitSha) -> PullRequestDiff:
        logger.info("ChangesetFetcher.fetch(pr_id=%s, sha=%s)", pr_id, sha.value[:7])
        diff_path = f"/repos/{pr_id.repository}/pulls/{pr_id.number}.diff"
        headers = {"Accept": "application/vnd.github.diff"}
        raw_diff = self._client.get_raw(diff_path, headers=headers, repo=pr_id.repository)

        if not raw_diff or len(raw_diff.strip()) < 50:
            raise EmptyDiffError(
                f"Diff for {pr_id} at {sha} is empty or too short"
            )

        file_paths: set[str] = set()
        deleted_paths: set[str] = set()

        logger.debug("First 500 chars of diff: %s", raw_diff[:500])

        for match in _DIFF_FILE_PATH_RE.finditer(raw_diff):
            new_path = match.group(2)
            old_path = match.group(1)
            if new_path and new_path != "/dev/null":
                file_paths.add(new_path)
            elif old_path and old_path != "/dev/null":
                deleted_paths.add(old_path)

        logger.debug(
            "Diff files: %d changed (%s), %d deleted (%s)",
            len(file_paths), sorted(file_paths),
            len(deleted_paths), sorted(deleted_paths),
        )

        file_contents: dict[str, str] = {}
        for file_path in sorted(file_paths):
            contents_path = f"/repos/{pr_id.repository}/contents/{file_path}?ref={sha.value}"
            try:
                content = self._client.get_raw(
                    contents_path,
                    headers={"Accept": "application/vnd.github.raw+json"},
                    repo=pr_id.repository,
                )
                file_contents[file_path] = content
                logger.debug("Fetched content for %s: %d chars", file_path, len(content))
            except Exception:
                logger.debug("Skipping unreadable file: %s", file_path)

        commit_messages = self._fetch_commit_messages(pr_id)

        diff = PullRequestDiff(
            pr_id=pr_id,
            head_sha=sha,
            diff_content=raw_diff,
            file_contents=file_contents,
            commit_messages=commit_messages,
        )
        logger.info(
            "ChangesetFetcher return: pr=%s sha=%s diff=%d chars files=%d commits=%d",
            pr_id, sha.value[:7],
            len(raw_diff), len(file_contents), len(commit_messages),
        )
        return diff
