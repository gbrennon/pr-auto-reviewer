"""Tests for legacy encrypted state migration during service wiring."""

from dataclasses import replace
from pathlib import Path

from pr_auto_reviewer.domain import CommitSha, PullRequest, PullRequestId
from pr_auto_reviewer.infrastructure.config import Config
from pr_auto_reviewer.infrastructure.container._core_services import wire_core_services
from pr_auto_reviewer.infrastructure.persistence.sqlite_persistence import (
    LEGACY_STORAGE_ENCRYPTION_KEY,
    SqlitePullRequestRepository,
)

pytest_plugins = (
    "tests.pr_auto_reviewer.infrastructure.container.core_services._helpers",
)


class TestStorageKeyMigration:
    """Verify wired repositories can read state created before key setup."""

    def test_wiring_migrates_legacy_state_before_repository_reads(
        self,
        forgejo_config: Config,
        repo_context,
        tmp_path: Path,
    ) -> None:
        pull_request = PullRequest(
            id=PullRequestId(repository="owner/repo", number=42),
            title="Legacy state",
            head_sha=CommitSha(value="legacy-sha"),
        )
        SqlitePullRequestRepository(
            tmp_path / "state.sqlite3",
            LEGACY_STORAGE_ENCRYPTION_KEY,
        ).save(pull_request)
        config = replace(forgejo_config, storage_encryption_key="configured-key")

        result = wire_core_services(config, repo_context, _config_dir=tmp_path)

        assert result.pr_repository.find(pull_request.id) == pull_request
