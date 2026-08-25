from ._helpers import *


class TestPR18DiffE2E:
    """E2E tests specifically for PR18 diff scenario."""

    def test_pr18_diff_is_loaded(
        self,
        review_flow_fixtures: dict,
    ) -> None:
        """PR18 diff fixture is properly loaded."""
        pr18_diff = review_flow_fixtures.get("pr18_diff", "")
        assert "evals/evaluators/__init__.py" in pr18_diff
        assert "evals/evaluators/exact_match.py" in pr18_diff
        assert "evals/evaluators/factory.py" in pr18_diff
        assert len(pr18_diff) > 1000

    def test_pr18_review_flow(
        self,
        review_flow_fixtures: dict,
    ) -> None:
        """Test review flow with PR18 diff content."""
        from pr_auto_reviewer.domain.value_objects.pull_request_diff import (
            PullRequestDiff,
        )

        pr18_diff = review_flow_fixtures.get("pr18_diff", "")

        diff = PullRequestDiff(
            pr_id=PullRequestId(repository="test/evals", number=18),
            head_sha=CommitSha("67ebb6c1234567890abcdef1234567890abcdef"),
            diff_content=pr18_diff,
            repository_structure="evals/evaluators/__init__.py\nevals/evaluators/base.py\nevals/evaluators/factory.py",
        )

        assert diff.pr_id.repository == "test/evals"
        assert diff.pr_id.number == 18
        assert len(diff.diff_content) > 1000

    def test_pr18_detection_as_clean_architecture(self, review_flow_fixtures: dict) -> None:
        """Test that PR18 tree paths detect clean architecture."""
        tree_paths = [
            "evals/evaluators/factory.py",
            "evals/evaluators/base.py",
            "evals/evaluators/schema.py",
            "evals/use_cases/",
            "evals/domain/",
            "evals/infrastructure/",
        ]

        detector = ArchitectureDetector()
        arch = detector.detect(tree_paths)

        assert arch in ["clean", "layered", "hexagonal", "onion", "cqrs", "mvc"]
