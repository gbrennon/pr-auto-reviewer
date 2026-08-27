from ._helpers import *


class TestTrimRepoStructure:
    def test_unchanged_when_under_limit(self):
        structure = "\n".join(f"file{i}.py" for i in range(5))
        result = _trim_repo_structure(structure, max_lines=10)
        assert result == structure

    def test_truncates_when_over_limit(self):
        structure = "\n".join(f"file{i}.py" for i in range(200))
        result = _trim_repo_structure(structure, max_lines=50)
        assert "..." in result
        assert result.count("\n") < 100

