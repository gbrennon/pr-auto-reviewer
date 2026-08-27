from ._helpers import *


class TestRunGitPrRangeScoping:
    """Bare diff/log resolve to the PR base→head range when a base SHA is set."""

    def test_diff_when_bare_and_base_sha_then_scoped_to_pr_range(self, git_pr_repo, git_repo) -> None:
        result = git_pr_repo.service(git_repo).run_git("diff --name-only")

        assert result["status"] == "ok"
        assert "src/new.py" in result["output"]

    def test_log_when_bare_and_base_sha_then_scoped_to_pr_range(self, git_pr_repo, git_repo) -> None:
        result = git_pr_repo.service(git_repo).run_git("log --oneline")

        assert result["status"] == "ok"
        assert "add feature" in result["output"]
        assert "init" not in result["output"]

    def test_diff_when_explicit_range_then_left_untouched(self, git_pr_repo, git_repo) -> None:
        result = git_pr_repo.service(git_repo).run_git("diff --name-only HEAD~1..HEAD")

        assert result["status"] == "ok"
        assert "src/new.py" in result["output"]

    def test_diff_when_base_sha_absent_then_not_scoped(self, git_repo) -> None:
        result = _service(git_repo).run_git("diff --name-only")

        assert result["status"] == "ok"
        assert result["output"] == ""

    def test_status_when_base_sha_then_not_scoped(self, git_pr_repo, git_repo) -> None:
        result = git_pr_repo.service(git_repo).run_git("status --short")

        assert result["status"] == "ok"
        assert result["output"] == ""

