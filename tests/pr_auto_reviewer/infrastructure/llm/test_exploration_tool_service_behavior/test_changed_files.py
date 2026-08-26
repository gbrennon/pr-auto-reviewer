from ._helpers import *


class TestChangedFiles:
    """Exercises the changed-files report."""

    def test_get_changed_files_when_none_then_empty(self, repo) -> None:
        result = _service(repo).get_changed_files()

        assert result == {"status": "ok", "files": []}

    def test_get_changed_files_when_provided_then_returns(self, repo) -> None:
        result = ExplorationToolService(repo, changed_files=["a.py", "b.py"]).get_changed_files()

        assert result == {"status": "ok", "files": ["a.py", "b.py"]}

    def test_resolve_safe_when_absolute_inside_repo_then_allowed(self, repo) -> None:
        service = _service(repo)
        path = service._resolve_safe(str(repo / "src" / "app.py"))

        assert path is not None
        assert path.name == "app.py"

