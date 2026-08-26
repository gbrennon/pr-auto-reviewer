from ._helpers import *


class TestRunGit:
    """Exercises read-only git execution."""

    def test_git_when_allowed_subcommand_then_output(self, git_repo) -> None:
        result = _service(git_repo).run_git("status --short")

        assert result["status"] == "ok"
        assert result["subcommand"] == "status"

    def test_git_when_log_then_commits(self, git_repo) -> None:
        result = _service(git_repo).run_git("log --oneline")

        assert result["status"] == "ok"
        assert "init" in result["output"]

    def test_git_when_disallowed_subcommand_then_error(self, git_repo) -> None:
        result = _service(git_repo).run_git("push origin main")

        assert result["status"] == "error"
        assert "not allowed" in result["error"]

    def test_git_when_empty_args_then_error(self, git_repo) -> None:
        result = _service(git_repo).run_git("  ")

        assert result["status"] == "error"
        assert "Empty" in result["error"]

    def test_git_when_fails_then_error(self, repo) -> None:
        result = _service(repo).run_git("show HEAD")

        assert result["status"] == "error"

