"""LocalChangesetFetcher — implements ChangesetFetcherPort using a local git clone."""

from __future__ import annotations

import logging
import re

from pr_auto_reviewer.application.ports.outbound.changeset_fetcher_port import (
    ChangesetFetcherPort,
)
from pr_auto_reviewer.application.ports.outbound.clone_url_resolver_port import (
    CloneUrlResolverPort,
)
from pr_auto_reviewer.application.ports.outbound.local_repository_port import (
    LocalRepositoryPort,
)
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId

logger = logging.getLogger(__name__)

_DIFF_FILE_PATH_RE = re.compile(
    r"^\s*diff --git a/(.+?)\s+b/(.+?)$", re.MULTILINE
)
_DELETION_RE = re.compile(
    r"^--- a/(\S+).*$\n^\+\+\+ /dev/null$", re.MULTILINE
)



class LocalChangesetFetcher(ChangesetFetcherPort):
    """Fetches PR changesets from a locally-cloned git repository."""

    def __init__(
        self,
        local_repository: LocalRepositoryPort,
        url_resolver: CloneUrlResolverPort,
    ) -> None:
        self._local_repo = local_repository
        self._url_resolver = url_resolver

    def fetch(self, pr_id: PullRequestId, sha: CommitSha) -> PullRequestDiff:
        clone_url = self._url_resolver.resolve(pr_id.repository)
        logger.info(
            "LocalChangesetFetcher cloning %s for PR %s",
            clone_url, pr_id,
        )

        repo_path = self._local_repo.clone(pr_id, clone_url)
        pr_head_ref = f"pr-{pr_id.number}"
        base_sha = self._local_repo.resolve_base_sha(repo_path, pr_id.number)

        logger.debug(
            "Using clone at %s (base=%s, head=%s)",
            repo_path, base_sha, pr_head_ref,
        )

        raw_diff = self._local_repo.compute_diff(
            repo_path, base_sha, pr_head_ref,
        )

        commit_messages = self._local_repo.commit_messages(
            repo_path, base_sha, pr_head_ref,
        )

        file_paths: set[str] = set()

        for match in _DIFF_FILE_PATH_RE.finditer(raw_diff):
            new_path = match.group(2)
            if new_path != "/dev/null":
                file_paths.add(new_path)

        for match in _DELETION_RE.finditer(raw_diff):
            file_paths.discard(match.group(1))

        file_contents: dict[str, str] = {}
        for file_path in sorted(file_paths):
            try:
                file_contents[file_path] = self._local_repo.read_file(
                    repo_path, file_path, ref=pr_head_ref,
                )
            except RuntimeError:
                logger.warning(
                    "Could not read file %s at ref %s", file_path, pr_head_ref,
                )

        return PullRequestDiff(
            pr_id=pr_id,
            head_sha=sha,
            diff_content=raw_diff,
            file_contents=file_contents,
            commit_messages=commit_messages,
            clone_path=repo_path,
        )
