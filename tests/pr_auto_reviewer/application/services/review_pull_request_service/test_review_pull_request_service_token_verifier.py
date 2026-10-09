from pathlib import Path, PosixPath

from pr_auto_reviewer.domain.messages.commands.audit_remediation_command import (
    AuditRemediationCommand,
)
from pr_auto_reviewer.domain.messages.commands.run_multi_phase_review_command import (
    RunMultiPhaseReviewCommand,
)
from pr_auto_reviewer.domain.value_objects.review_audit_result import (
    ReviewAuditResult,
)
from pr_auto_reviewer.domain.value_objects.review_plan import ReviewPlan

from ._helpers import *


class TestReviewPullRequestServiceTokenVerifier:
    def test_execute_with_token_verifier(
        self, request,
    ):
        mock_token_verifier = request.getfixturevalue("mock_token_verifier")
        mock_pr_repository = request.getfixturevalue("mock_pr_repository")
        mock_changeset_fetcher = request.getfixturevalue("mock_changeset_fetcher")
        mock_review_context_factory = request.getfixturevalue("mock_review_context_factory")
        mock_llm_review = request.getfixturevalue("mock_llm_review")
        mock_review_publisher = request.getfixturevalue("mock_review_publisher")
        cmd = _cmd()
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = _diff_fixture(cmd.pr_id, cmd.head_sha)
        mock_llm_review.review_prompt.return_value = _review(ReviewVerdict.APPROVED)

        service = ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
            token_verifier=mock_token_verifier,
        )

        service.execute(cmd)

        mock_token_verifier.verify.assert_called_with(cmd.pr_id)

    def test_single_turn_review_when_no_command_bus(
            self, request,
    ):
        """Test review flow when no command_bus is available (single-turn review)."""
        mock_pr_repository = request.getfixturevalue("mock_pr_repository")
        mock_changeset_fetcher = request.getfixturevalue("mock_changeset_fetcher")
        mock_review_context_factory = request.getfixturevalue("mock_review_context_factory")
        mock_llm_review = request.getfixturevalue("mock_llm_review")
        mock_review_publisher = request.getfixturevalue("mock_review_publisher")
        cmd = _cmd()
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        mock_llm_review.review_prompt.return_value = _review(
            ReviewVerdict.APPROVED
        )

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
            command_bus=None,  # No command bus → single-turn review
        ).execute(cmd)

        mock_changeset_fetcher.fetch.assert_called_once()
        mock_review_context_factory.build.assert_called_once()
        mock_llm_review.review_prompt.assert_called_once()
        mock_review_publisher.publish.assert_called_once()
        mock_pr_repository.save.assert_called_once()
        assert mock_pr_repository.save.call_args.args[0].head_sha == cmd.head_sha



class TestSingleTurnFallback:
    def test_multi_phase_without_plan_falls_back_to_single_turn(
            self, request,
    ):
        """A command bus with no injected plan must not run empty-prompt phases."""
        mock_pr_repository = request.getfixturevalue("mock_pr_repository")
        mock_changeset_fetcher = request.getfixturevalue("mock_changeset_fetcher")
        mock_review_context_factory = request.getfixturevalue("mock_review_context_factory")
        mock_llm_review = request.getfixturevalue("mock_llm_review")
        mock_review_publisher = request.getfixturevalue("mock_review_publisher")
        cmd = _cmd()
        diff = PullRequestDiff(
            pr_id=cmd.pr_id,
            head_sha=cmd.head_sha,
            diff_content=(
                "diff --git a/src/a.py b/src/a.py\n"
                "+++ b/src/a.py\n"
                "@@ -0,0 +1 @@\n"
                "+x = 1\n"
            ),
            clone_path=Path("/repos/owner_repo_42"),
        )
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        mock_llm_review.review_prompt.return_value = _review(
            ReviewVerdict.APPROVED
        )
        command_bus = MagicMock()
        command_bus.dispatch.return_value = ReviewAuditResult(
            items=(), suggestions=(), lifecycles=(),
        )

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
            command_bus=command_bus,
        ).execute(cmd)

        mock_llm_review.review_prompt.assert_called_once()
        dispatched = command_bus.dispatch.call_args.args[0]
        assert isinstance(dispatched, AuditRemediationCommand)

    def test_multi_phase_dispatch_carries_base_sha(
            self, request,
    ):
        """The PR merge-base is forwarded into the RunMultiPhaseReviewCommand."""
        mock_pr_repository = request.getfixturevalue("mock_pr_repository")
        mock_changeset_fetcher = request.getfixturevalue("mock_changeset_fetcher")
        mock_review_context_factory = request.getfixturevalue("mock_review_context_factory")
        mock_llm_review = request.getfixturevalue("mock_llm_review")
        mock_review_publisher = request.getfixturevalue("mock_review_publisher")
        cmd = _cmd()
        diff = PullRequestDiff(
            pr_id=cmd.pr_id,
            head_sha=cmd.head_sha,
            base_sha=CommitSha(value="d896687cafc093f113ade5444f02df98fcfc9042"),
            diff_content=(
                "diff --git a/src/a.py b/src/a.py\n"
                "+++ b/src/a.py\n"
                "@@ -0,0 +1 @@\n"
                "+x = 1\n"
            ),
            clone_path=Path("/repos/owner_repo_42"),
        )
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        mock_llm_review.review_prompt.return_value = _review(
            ReviewVerdict.APPROVED
        )
        command_bus = MagicMock()
        command_bus.dispatch.return_value = _review(ReviewVerdict.APPROVED)
        plan = ReviewPlan(methodology="sub-agent-multi-phase", phases=())

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
            command_bus=command_bus,
            plan=plan,
        ).execute(cmd)

        dispatch_args, _ = command_bus.dispatch.call_args
        dispatched = dispatch_args[0]
        assert isinstance(dispatched, RunMultiPhaseReviewCommand)
        assert dispatched.base_sha == "d896687cafc093f113ade5444f02df98fcfc9042"
        assert dispatched.repo_path == PosixPath("/repos/owner_repo_42")



class TestMultiPhaseDispatchLogging:
    def test_logs_before_multi_phase_dispatch(
        self, request,
    ):
        caplog = request.getfixturevalue("caplog")
        mock_pr_repository = request.getfixturevalue("mock_pr_repository")
        mock_changeset_fetcher = request.getfixturevalue("mock_changeset_fetcher")
        mock_review_context_factory = request.getfixturevalue("mock_review_context_factory")
        mock_llm_review = request.getfixturevalue("mock_llm_review")
        mock_review_publisher = request.getfixturevalue("mock_review_publisher")
        cmd = _cmd()
        diff = PullRequestDiff(
            pr_id=cmd.pr_id,
            head_sha=cmd.head_sha,
            base_sha=CommitSha(value="base-sha"),
            diff_content="diff --git a/src/a.py b/src/a.py\n",
            clone_path=Path("/repos/owner_repo_42"),
        )
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        command_bus = MagicMock()

        def dispatch(command):
            if isinstance(command, AuditRemediationCommand):
                return ReviewAuditResult(
                    items=(), suggestions=(), lifecycles=(),
                )
            assert any(
                "Dispatching multi-phase review" in record.message
                for record in caplog.records
            )
            return _review(ReviewVerdict.APPROVED)

        command_bus.dispatch.side_effect = dispatch
        caplog.set_level(
            logging.INFO,
            logger="pr_auto_reviewer.application.services.review_pull_request_service",
        )

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
            command_bus=command_bus,
            plan=ReviewPlan(methodology="sub-agent-multi-phase", phases=()),
        ).execute(cmd)



class TestPriorFindingAuditGate:
    def test_multi_phase_audits_all_historical_sections_before_phases(
        self, mock_pr_repository, mock_changeset_fetcher, mock_review_publisher,
    ):
        cmd = _cmd()
        diff = PullRequestDiff(
            pr_id=cmd.pr_id,
            head_sha=cmd.head_sha,
            diff_content="""\
diff --git a/src/a.py b/src/a.py
+++ b/src/a.py
""",
            file_contents={"src/a.py": "x = 1\n"},
            clone_path=Path("/repos/owner_repo_42"),
        )
        changed_item = ReviewItem(
            severity="major", category="correctness", file_path="src/a.py",
            description="changed", id="aaaa",
        )
        unchanged_item = ReviewItem(
            severity="major", category="correctness", file_path="src/old.py",
            description="unchanged", id="bbbb",
        )
        suggestion = ReviewItem(
            severity="minor", category="style", file_path="src/old.py",
            description="suggestion", id="cccc",
        )
        existing = _pr(cmd.pr_id, _sha("old"))
        existing = existing.add_review(
            CodeReview(
                verdict=ReviewVerdict.APPROVED,
                items=[changed_item, unchanged_item],
                suggestions=[suggestion],
                summary="Looks good",
                reason="test reason",
                model_used="test",
            ),
            _sha("old"),
        )
        mock_pr_repository.find.return_value = existing
        mock_changeset_fetcher.fetch.return_value = diff
        command_bus = MagicMock()
        command_bus.dispatch.side_effect = [
            ReviewAuditResult(
                items=(changed_item, unchanged_item),
                suggestions=(suggestion,),
                lifecycles=(),
            ),
            _review(),
        ]

        ReviewPullRequestService(
            mock_pr_repository, mock_changeset_fetcher, MagicMock(), MagicMock(),
            mock_review_publisher, command_bus=command_bus,
            plan=ReviewPlan(methodology="sub-agent-multi-phase", phases=()),
        ).execute(cmd)

        audit_command = command_bus.dispatch.call_args_list[0].args[0]
        review_command = command_bus.dispatch.call_args_list[1].args[0]
        assert isinstance(audit_command, AuditRemediationCommand)
        assert audit_command.prior_items == [changed_item, unchanged_item]
        assert audit_command.prior_suggestions == [suggestion]
        assert audit_command.prior_lifecycles == existing.lifecycles
        assert isinstance(review_command, RunMultiPhaseReviewCommand)
        assert review_command.prior_items == [changed_item, unchanged_item]
        assert review_command.prior_suggestions == [suggestion]
