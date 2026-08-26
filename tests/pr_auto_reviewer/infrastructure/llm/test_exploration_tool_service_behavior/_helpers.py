"""Shared helpers, fixtures, and imports for the split test modules."""

import pytest

from pr_auto_reviewer.domain.value_objects.tool_call import ToolCall
from pr_auto_reviewer.infrastructure.llm.exploration_tool_service import (
    ExplorationToolService,
)


@pytest.fixture
def repo(tmp_path):
    """A temporary repo with source files, a binary, and git history."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "app.py").write_text("\n".join(f"line{i}" for i in range(1, 21)))
    (src / "main.py").write_text("import app\n")
    (tmp_path / "data.bin").write_bytes(b"\xff\xfe\x00\x01")
    return tmp_path


@pytest.fixture
def git_repo(repo, monkeypatch):
    """The repo initialized as a git worktree with one commit."""
    import subprocess

    monkeypatch.setenv("GIT_AUTHOR_NAME", "test")
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "test@example.com")
    monkeypatch.setenv("GIT_COMMITTER_NAME", "test")
    monkeypatch.setenv("GIT_COMMITTER_EMAIL", "test@example.com")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=repo, check=True)
    return repo


@pytest.fixture
def git_pr_repo(git_repo, monkeypatch):
    """A PR-shaped clone: base commit, then a head commit checked out at HEAD.

    The worktree is clean at the head commit, so a bare ``git diff`` shows
    nothing — exactly the situation the base-SHA scoping exists to fix.
    """
    import subprocess as sp

    base_sha = sp.run(
        ["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True, check=True
    ).stdout.strip()
    (git_repo / "src" / "new.py").write_text("CHANGED\n")
    sp.run(["git", "add", "-A"], cwd=git_repo, check=True)
    sp.run(
        ["git", "commit", "-q", "-m", "add feature"],
        cwd=git_repo, check=True,
    )
    return _ServiceWithBase(base_sha)


def _service(repo):
    return ExplorationToolService(repo)


__all__ = ['ExplorationToolService', 'ToolCall', '_ServiceWithBase', '_service', 'git_pr_repo', 'git_repo', 'pytest', 'repo']


class _ServiceWithBase:
    """Holds the base SHA together with a convenience constructor."""

    def __init__(self, base_sha):
        self.base_sha = base_sha

    def service(self, repo):
        return ExplorationToolService(repo, base_sha=self.base_sha)
