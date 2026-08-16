"""Fake local repository for LocalChangesetFetcher tests."""

from __future__ import annotations

from pathlib import Path


class FakeLocalRepository:
    """Fake implementing LocalRepositoryPort with configurable returns and call tracking.

    Each method records calls as ``(args_tuple, kwargs_dict)`` in a dedicated
    ``*_calls`` list attribute.  Return values are configured via corresponding
    ``*_return`` attributes that accept plain values, callables, exceptions,
    or (for ``read_file_return``) a sequential list.
    """

    _read_file_idx: int

    def __init__(
        self,
        clone_return: Path | None = None,
        compute_diff_return: str | BaseException = "",
        commit_messages_return: list[str] | None = None,
        resolve_base_sha_return: str = "abc123",
        read_file_return: str | list | BaseException = "",
        last_clone_path_return: Path | None = None,
        list_tree_return: list[str] | BaseException | None = None,
    ) -> None:
        self.clone_return = clone_return or Path("/tmp/clone/repo")
        self.compute_diff_return = compute_diff_return
        self.commit_messages_return = commit_messages_return or ["fix: stuff"]
        self.resolve_base_sha_return = resolve_base_sha_return
        self.read_file_return = read_file_return
        self._last_clone_path = last_clone_path_return
        self.list_tree_return = list_tree_return or ["src/main.py", "src/utils.py", "CONVENTIONS.md"]

        self.clone_calls: list[tuple[tuple, dict]] = []
        self.remove_calls: list[tuple[tuple, dict]] = []
        self.compute_diff_calls: list[tuple[tuple, dict]] = []
        self.commit_messages_calls: list[tuple[tuple, dict]] = []
        self.resolve_base_sha_calls: list[tuple[tuple, dict]] = []
        self.read_file_calls: list[tuple[tuple, dict]] = []
        self.list_tree_calls: list[tuple[tuple, dict]] = []

        self._read_file_idx = 0

    @property
    def last_clone_path(self) -> Path | None:
        return self._last_clone_path

    def clone(self, pr_id: object, clone_url: str) -> Path:
        self.clone_calls.append(((pr_id, clone_url), {}))
        return self.clone_return

    def remove(self, repo_path: Path) -> None:
        self.remove_calls.append(((repo_path,), {}))
        return None

    def compute_diff(
        self, repo_path: Path, base_sha: str, head_sha: str,
    ) -> str:
        self.compute_diff_calls.append(((repo_path, base_sha, head_sha), {}))
        if isinstance(self.compute_diff_return, BaseException):
            raise self.compute_diff_return
        return self.compute_diff_return

    def commit_messages(
        self, repo_path: Path, base_sha: str, head_sha: str,
    ) -> list[str]:
        self.commit_messages_calls.append(((repo_path, base_sha, head_sha), {}))
        return self.commit_messages_return

    def resolve_base_sha(self, repo_path: Path, pr_number: int) -> str:
        self.resolve_base_sha_calls.append(((repo_path, pr_number), {}))
        return self.resolve_base_sha_return

    def read_file(
        self, repo_path: Path, file_path: str, ref: str = "HEAD",
    ) -> str:
        self.read_file_calls.append(((repo_path, file_path), {"ref": ref}))
        if isinstance(self.read_file_return, list):
            result = self.read_file_return[self._read_file_idx]
            self._read_file_idx += 1
            if isinstance(result, BaseException):
                raise result
            return result
        if isinstance(self.read_file_return, BaseException):
            raise self.read_file_return
        return self.read_file_return

    def list_tree(
        self, repo_path: Path, ref: str = "HEAD",
    ) -> list[str]:
        self.list_tree_calls.append(((repo_path,), {"ref": ref}))
        if isinstance(self.list_tree_return, BaseException):
            raise self.list_tree_return
        return self.list_tree_return
