from ._helpers import *


class TestConstruction:
    """Exercises __init__ validation."""

    def test_init_when_empty_path_then_raises(self) -> None:
        with pytest.raises(ValueError):
            ExplorationToolService("")

    def test_init_when_missing_dir_then_raises(self, tmp_path) -> None:
        with pytest.raises(ValueError):
            ExplorationToolService(tmp_path / "nope")

    def test_init_when_valid_then_sets_root(self, repo) -> None:
        service = _service(repo)

        assert service._repo_root == repo.resolve()
        assert service._changed_files == []

