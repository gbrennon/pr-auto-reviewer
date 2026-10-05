from ._helpers import *

_REVIEW_SERVICE_LOGGER = (
    "pr_auto_reviewer.application.services.review_pull_request_service"
)

class TestReviewPullRequestService:
    def test_new_pr_full_flow(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
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
        ).execute(cmd)

        mock_pr_repository.find.assert_called_once_with(cmd.pr_id)
        mock_changeset_fetcher.fetch.assert_called_once_with(
            cmd.pr_id, cmd.head_sha
        )
        mock_review_context_factory.build.assert_called_once()
        mock_llm_review.review_prompt.assert_called_once()
        mock_review_publisher.publish.assert_called_once()
        args, _ = mock_review_publisher.publish.call_args
        assert args[2] is not None, "diff should be passed to publisher"
        mock_pr_repository.save.assert_called_once()
        assert mock_pr_repository.save.call_args.args[0].head_sha == cmd.head_sha

    def test_already_reviewed_sha_skips_review(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        cmd = _cmd()
        existing = _pr(cmd.pr_id, cmd.head_sha)
        existing = existing.add_review(_review(), cmd.head_sha)
        mock_pr_repository.find.return_value = existing

        reviewed = ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        assert reviewed is False
        mock_changeset_fetcher.fetch.assert_not_called()
        mock_review_context_factory.build.assert_not_called()
        mock_llm_review.review_prompt.assert_not_called()
        mock_review_publisher.publish.assert_not_called()
        mock_pr_repository.save.assert_called_once()

    def test_force_bypasses_idempotency_guard(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        sha = _sha()
        cmd = ReviewPullRequestCommand(
            pr_id=_pr_id(),
            head_sha=sha,
            title="Add feature X",
            force=True,
        )
        existing = _pr(cmd.pr_id, sha)
        existing = existing.add_review(_review(), sha)
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        mock_pr_repository.find.return_value = existing
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
        ).execute(cmd)

        mock_changeset_fetcher.fetch.assert_called_once()
        mock_review_context_factory.build.assert_called_once()
        mock_llm_review.review_prompt.assert_called_once()
        mock_review_publisher.publish.assert_called_once()
        mock_pr_repository.save.assert_called_once()

    def test_stale_review_request_does_not_bypass_same_sha_guard(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        sha = _sha()
        cmd = ReviewPullRequestCommand(
            pr_id=_pr_id(),
            head_sha=sha,
            title="Add feature X",
            review_requested=True,
        )
        existing = PullRequest(
            id=cmd.pr_id, title=cmd.title, head_sha=sha,
        ).add_review(_review(), sha)
        mock_pr_repository.find.return_value = existing

        ReviewPullRequestService(
            mock_pr_repository, mock_changeset_fetcher,
            mock_review_context_factory, mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        mock_changeset_fetcher.fetch.assert_not_called()
        mock_review_context_factory.build.assert_not_called()
        mock_llm_review.review_prompt.assert_not_called()
        mock_review_publisher.publish.assert_not_called()
        mock_pr_repository.save.assert_called_once()

    def test_new_review_request_event_bypasses_same_sha_guard(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        sha = _sha()
        cmd = ReviewPullRequestCommand(
            pr_id=_pr_id(),
            head_sha=sha,
            title="Add feature X",
            review_requested=True,
            review_request_event_id=2,
        )
        existing = PullRequest(
            id=cmd.pr_id,
            title=cmd.title,
            head_sha=sha,
            last_review_request_event_id=1,
        ).add_review(_review(), sha)
        mock_pr_repository.find.return_value = existing
        mock_changeset_fetcher.fetch.return_value = _diff_fixture(
            cmd.pr_id, cmd.head_sha
        )
        mock_llm_review.review_prompt.return_value = _review(
            ReviewVerdict.APPROVED
        )

        ReviewPullRequestService(
            mock_pr_repository, mock_changeset_fetcher,
            mock_review_context_factory, mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        mock_review_publisher.publish.assert_called_once()

    def test_no_re_review_when_review_requested_false(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        sha = _sha()
        cmd = ReviewPullRequestCommand(
            pr_id=_pr_id(),
            head_sha=sha,
            title="Add feature X",
            review_requested=False,
        )
        existing = PullRequest(
            id=cmd.pr_id, title=cmd.title, head_sha=sha,
        )
        existing = existing.add_review(_review(), sha)
        mock_pr_repository.find.return_value = existing

        ReviewPullRequestService(
            mock_pr_repository, mock_changeset_fetcher,
            mock_review_context_factory, mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        mock_changeset_fetcher.fetch.assert_not_called()
        mock_review_context_factory.build.assert_not_called()
        mock_llm_review.review_prompt.assert_not_called()
        mock_review_publisher.publish.assert_not_called()
        mock_pr_repository.save.assert_called_once()

    def test_empty_diff_raises(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = PullRequestDiff(
            pr_id=_pr_id(),
            head_sha=_sha(),
            diff_content="   \n ",
        )
        svc = ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        )
        with pytest.raises(EmptyDiffError):
            svc.execute(_cmd())

    def test_existing_pr_new_sha_runs_full_flow(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        old, new = _sha("old111"), _sha("new222")
        cmd = _cmd(sha=new)
        existing = _pr(cmd.pr_id, old)
        existing = existing.add_review(_review(ReviewVerdict.CHANGES_REQUESTED), old)
        mock_pr_repository.find.return_value = existing
        mock_changeset_fetcher.fetch.return_value = _diff_fixture(
            cmd.pr_id, cmd.head_sha
        )
        mock_llm_review.review_prompt.return_value = _review(
            ReviewVerdict.APPROVED
        )

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        mock_changeset_fetcher.fetch.assert_called_once()
        mock_review_context_factory.build.assert_called_once()
        mock_llm_review.review_prompt.assert_called_once()
        mock_review_publisher.publish.assert_called_once()

    def test_debug_logs_review_complete_summary(
        self, caplog, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        cmd = _cmd()
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        mock_llm_review.review_prompt.return_value = _review(
            ReviewVerdict.CHANGES_REQUESTED
        )

        caplog.set_level(logging.DEBUG, logger=_REVIEW_SERVICE_LOGGER)
        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        summaries = [
            r.message for r in caplog.records if "REVIEW COMPLETE" in r.message
        ]
        assert len(summaries) == 1
        assert "verdict=changes_requested" in summaries[0]
        assert "items=0" in summaries[0]
        assert "summary='Looks good'" in summaries[0]

    def test_review_complete_summary_not_logged_at_info(
        self, caplog, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        cmd = _cmd()
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        mock_llm_review.review_prompt.return_value = _review()

        caplog.set_level(logging.INFO, logger=_REVIEW_SERVICE_LOGGER)
        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        summaries = [
            r.message for r in caplog.records if "REVIEW COMPLETE" in r.message
        ]
        assert len(summaries) == 0

    def test_review_complete_summary_not_logged_when_skipped(
        self, caplog, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        cmd = _cmd()
        existing = _pr(cmd.pr_id, cmd.head_sha)
        existing = existing.add_review(_review(), cmd.head_sha)
        mock_pr_repository.find.return_value = existing

        caplog.set_level(logging.DEBUG, logger=_REVIEW_SERVICE_LOGGER)
        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        summaries = [
            r.message for r in caplog.records if "REVIEW COMPLETE" in r.message
        ]
        assert len(summaries) == 0

    def test_prompt_from_factory_is_sent_to_llm(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        cmd = _cmd()
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        prompt = ComposedPrompt(
            content="You are a code reviewer.\n\nReview this diff:\n+code",
            fragments_used=["solid", "python-errors"],
            total_tokens=100,
        )
        mock_review_context_factory.build.return_value = prompt
        mock_llm_review.review_prompt.return_value = _review()

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        mock_review_context_factory.build.assert_called_once()
        args, _ = mock_llm_review.review_prompt.call_args
        assert args[0] is prompt

    def test_factory_receives_diff_in_build_call(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        cmd = _cmd()
        diff = _diff_fixture(cmd.pr_id, cmd.head_sha)
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        mock_llm_review.review_prompt.return_value = _review()

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        mock_review_context_factory.build.assert_called_once()
        args, _ = mock_review_context_factory.build.call_args
        pr_id_arg, build_diff = args[0], args[1]
        assert build_diff is diff
        assert "diff --git" in build_diff.diff_content
        assert pr_id_arg == cmd.pr_id

    def test_adds_concrete_finding_for_noisy_info_log_when_llm_misses_it(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        cmd = _cmd()
        diff = PullRequestDiff(
            pr_id=cmd.pr_id,
            head_sha=cmd.head_sha,
            diff_content=(
                "diff --git a/src/client.py b/src/client.py\n"
                "+++ b/src/client.py\n"
                "@@ -1,2 +1,3 @@\n"
                '+        logger.info("GET %s params=%s", url, params)\n'
            ),
        )
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
        ).execute(cmd)

        _, kwargs = mock_review_publisher.publish.call_args
        review = kwargs.get("review") or mock_review_publisher.publish.call_args.args[1]
        assert len(review.items) == 1
        assert review.items[0].id
        assert review.items[0].file_path == "src/client.py"
        assert review.items[0].current_code == (
            '        logger.info("GET %s params=%s", url, params)'
        )
        assert review.items[0].suggested_fix == (
            '        logger.debug("GET %s params=%s", url, params)'
        )

    def test_adds_noisy_log_findings_before_llm_findings(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        cmd = _cmd()
        diff = PullRequestDiff(
            pr_id=cmd.pr_id,
            head_sha=cmd.head_sha,
            diff_content=(
                "diff --git a/src/client.py b/src/client.py\n"
                "+++ b/src/client.py\n"
                "@@ -1,2 +1,3 @@\n"
                '+        logger.info("GET %s params=%s", url, params)\n'
            ),
        )
        llm_review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            summary="LLM finding",
            items=[
                ReviewItem(id="id-1",
                    severity="minor",
                    category="quality",
                    file_path="src/other.py",
                    description="existing",
                    current_code="x = 1",
                    suggested_fix="x = 2",
                )
            ],
            reason="test reason",
            model_used="test model",
        )
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        mock_llm_review.review_prompt.return_value = llm_review

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        args, _ = mock_review_publisher.publish.call_args
        review = args[1]
        assert len(review.items) == 2
        assert review.items[0].file_path == "src/client.py"
        assert review.items[1].file_path == "src/other.py"

    def test_skips_log_info_without_noisy_marker(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        """A logger.info() line without noisy markers does not produce a finding."""
        cmd = _cmd()
        diff = PullRequestDiff(
            pr_id=cmd.pr_id,
            head_sha=cmd.head_sha,
            diff_content=(
                "diff --git a/src/client.py b/src/client.py\n"
                "+++ b/src/client.py\n"
                "@@ -1,2 +1,3 @@\n"
                '+        logger.info("processing complete without markers")\n'
            ),
        )
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
        ).execute(cmd)

        args, _ = mock_review_publisher.publish.call_args
        review = args[1]
        assert len(review.items) == 0

    def test_limits_noisy_log_findings_to_five(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        """Noisy log detection caps at 5 findings."""
        cmd = _cmd()
        diff = PullRequestDiff(
            pr_id=cmd.pr_id,
            head_sha=cmd.head_sha,
            diff_content=(
                "diff --git a/src/app.py b/src/app.py\n"
                "+++ b/src/app.py\n"
                "@@ -1,10 +1,10 @@\n"
                '+        logger.info("GET %s", url)\n'
                '+        logger.info("POST %s", url)\n'
                '+        logger.info("return: %s", result)\n'
                '+        logger.info("keys=%s", data.keys())\n'
                '+        logger.info("chars=%s", text)\n'
                '+        logger.info("tokens=%s", tokens)\n'
            ),
        )
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
        ).execute(cmd)

        args, _ = mock_review_publisher.publish.call_args
        review = args[1]
        assert len(review.items) == 5

    def test_preserves_changes_requested_verdict_when_adding_deterministic_findings(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        """LLM returns CHANGES_REQUESTED + diff triggers noisy-log detection
        → verdict stays CHANGES_REQUESTED after _add_deterministic_findings."""
        cmd = _cmd()
        diff = PullRequestDiff(
            pr_id=cmd.pr_id,
            head_sha=cmd.head_sha,
            diff_content=(
                "diff --git a/src/client.py b/src/client.py\n"
                "+++ b/src/client.py\n"
                "@@ -1,2 +1,3 @@\n"
                '+        logger.info("GET %s params=%s", url, params)\n'
            ),
        )
        llm_review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            summary="Needs work",
            items=[
                ReviewItem(id="id-1",
                    severity="blocker",
                    category="bug",
                    file_path="src/other.py",
                    description="Null dereference",
                    current_code="x = None; x.foo()",
                    suggested_fix="guard with if x is not None",
                ),
                ReviewItem(id="id-2",
                    severity="major",
                    category="quality",
                    file_path="src/other.py",
                    description="Magic number",
                    current_code="sleep(300)",
                    suggested_fix="sleep(TIMEOUT)",
                ),
                ReviewItem(id="id-3",
                    severity="minor",
                    category="style",
                    file_path="src/other.py",
                    description="Bad variable name",
                    current_code="x = 1",
                    suggested_fix="count = 1",
                ),
                ReviewItem(id="id-4",
                    severity="minor",
                    category="quality",
                    file_path="src/other.py",
                    description="Unused import",
                    current_code="import os",
                    suggested_fix="",
                ),
            ],
            reason="test reason",
            model_used="test model",
        )
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        mock_llm_review.review_prompt.return_value = llm_review

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        args, _ = mock_review_publisher.publish.call_args
        review = args[1]
        assert review.verdict == ReviewVerdict.CHANGES_REQUESTED, (
            f"Expected CHANGES_REQUESTED but got {review.verdict}"
        )
        assert len(review.items) == 5, (
            f"Expected 5 items (4 LLM + 1 deterministic), got {len(review.items)}"
        )

    def test_published_review_has_unique_ids_when_llm_duplicates(
        self, mock_pr_repository, mock_changeset_fetcher,
        mock_review_context_factory, mock_llm_review, mock_review_publisher,
    ):
        """The guard rewrites duplicate/empty LLM ids and keeps publish/persist in sync."""
        cmd = _cmd()
        diff = PullRequestDiff(
            pr_id=cmd.pr_id,
            head_sha=cmd.head_sha,
            diff_content=(
                "diff --git a/src/client.py b/src/client.py\n"
                "+++ b/src/client.py\n"
                "@@ -1,2 +1,3 @@\n"
                '+        x = resolve(url, params)\n'
            ),
        )
        llm_review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            summary="LLM finding",
            items=[
                ReviewItem(id="dup",
                    severity="minor",
                    category="quality",
                    file_path="src/other.py",
                    description="one",
                    current_code="x = 1",
                    suggested_fix="x = 2",
                ),
                ReviewItem(id="dup",
                    severity="minor",
                    category="quality",
                    file_path="src/other.py",
                    description="two",
                    current_code="y = 1",
                    suggested_fix="y = 2",
                ),
                ReviewItem(id="",
                    severity="minor",
                    category="quality",
                    file_path="src/other.py",
                    description="three",
                    current_code="z = 1",
                    suggested_fix="z = 2",
                ),
            ],
            reason="test reason",
            model_used="test model",
        )
        mock_pr_repository.find.return_value = None
        mock_changeset_fetcher.fetch.return_value = diff
        mock_llm_review.review_prompt.return_value = llm_review

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        args, _ = mock_review_publisher.publish.call_args
        review = args[1]
        assert len({item.id for item in review.items}) == len(review.items)
        assert all(item.id for item in review.items)

        saved_pr = mock_pr_repository.save.call_args.args[0]
        saved_items = saved_pr.reviews[-1].items
        assert {item.id for item in saved_items} == {item.id for item in review.items}


    def test_republishes_prior_items_and_keeps_open_blocker_blocking(
        self,
        mock_pr_repository,
        mock_changeset_fetcher,
        mock_review_context_factory,
        mock_llm_review,
        mock_review_publisher,
    ) -> None:
        blocking = ReviewItem(
            id="block-1",
            severity=ItemSeverity.MAJOR,
            category=IssueCategory.BUG,
            file_path="src/app.py",
            description="Handle the failure path",
        )
        prior = _pr(_pr_id(), _sha("old111")).add_review(
            _review(ReviewVerdict.CHANGES_REQUESTED, [blocking]),
            _sha("old111"),
        ).with_unresolved_blocking("block-1")
        cmd = _cmd(pr_id=prior.id, sha=_sha("new222"))
        mock_pr_repository.find.return_value = prior
        mock_changeset_fetcher.fetch.return_value = _diff_fixture(
            cmd.pr_id, cmd.head_sha,
        )
        mock_llm_review.review_prompt.return_value = _review(
            ReviewVerdict.APPROVED,
        )

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        published = mock_review_publisher.publish.call_args.args[1]
        assert [item.id for item in published.items] == ["block-1"]
        assert published.items[0].status == "open"
        assert published.verdict == ReviewVerdict.CHANGES_REQUESTED
        saved_pr = mock_pr_repository.save.call_args.args[0]
        assert saved_pr.unresolved_blocking_ids == frozenset({"block-1"})

    def test_republishes_all_items_with_resolved_status_after_fix(
        self,
        mock_pr_repository,
        mock_changeset_fetcher,
        mock_review_context_factory,
        mock_llm_review,
        mock_review_publisher,
    ) -> None:
        blocking = ReviewItem(
            id="block-1",
            severity=ItemSeverity.MAJOR,
            category=IssueCategory.BUG,
            file_path="src/app.py",
            description="Handle the failure path",
        )
        prior = _pr(_pr_id(), _sha("old111")).add_review(
            _review(ReviewVerdict.CHANGES_REQUESTED, [blocking]),
            _sha("old111"),
        ).with_unresolved_blocking("block-1")
        resolved = ReviewItem(
            id="block-1",
            severity=ItemSeverity.MAJOR,
            category=IssueCategory.BUG,
            file_path="src/app.py",
            description="Handle the failure path",
            status="resolved",
        )
        cmd = _cmd(pr_id=prior.id, sha=_sha("new222"))
        mock_pr_repository.find.return_value = prior
        mock_changeset_fetcher.fetch.return_value = _diff_fixture(
            cmd.pr_id, cmd.head_sha,
        )
        mock_llm_review.review_prompt.return_value = _review(
            ReviewVerdict.APPROVED, [resolved],
        )

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        published = mock_review_publisher.publish.call_args.args[1]
        assert [item.id for item in published.items] == ["block-1"]
        assert published.items[0].status == "resolved"
        assert published.verdict == ReviewVerdict.APPROVED
        saved_pr = mock_pr_repository.save.call_args.args[0]
        assert not saved_pr.unresolved_blocking_ids

    def test_republishes_prior_suggestions_as_suggestions(
        self,
        mock_pr_repository,
        mock_changeset_fetcher,
        mock_review_context_factory,
        mock_llm_review,
        mock_review_publisher,
    ) -> None:
        prior_item = ReviewItem(
            id="item-1",
            severity=ItemSeverity.MAJOR,
            category=IssueCategory.BUG,
            file_path="src/app.py",
            description="Handle the failure path",
        )
        prior_suggestion = ReviewItem(
            id="suggestion-1",
            severity=ItemSeverity.INFO,
            category=IssueCategory.STYLE,
            file_path="src/app.py",
            description="Consider a clearer name",
        )
        prior_review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            items=[prior_item],
            suggestions=[prior_suggestion],
            summary="Needs changes",
            model_used="test",
            reason="test reason",
        )
        prior = _pr(_pr_id(), _sha("old111")).add_review(
            prior_review,
            _sha("old111"),
        )
        cmd = _cmd(pr_id=prior.id, sha=_sha("new222"))
        mock_pr_repository.find.return_value = prior
        mock_changeset_fetcher.fetch.return_value = _diff_fixture(
            cmd.pr_id,
            cmd.head_sha,
        )
        mock_llm_review.review_prompt.return_value = _review(
            ReviewVerdict.APPROVED,
        )

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        published = mock_review_publisher.publish.call_args.args[1]

        assert [item.id for item in published.items] == ["item-1"]
        assert [item.id for item in published.suggestions] == ["suggestion-1"]

    def test_does_not_duplicate_reclassified_prior_suggestions(
        self,
        mock_pr_repository,
        mock_changeset_fetcher,
        mock_review_context_factory,
        mock_llm_review,
        mock_review_publisher,
    ) -> None:
        prior_suggestion = ReviewItem(
            id="shared-1",
            severity=ItemSeverity.INFO,
            category=IssueCategory.STYLE,
            file_path="src/app.py",
            description="Consider a clearer name",
        )
        prior_review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            suggestions=[prior_suggestion],
            summary="Looks good",
            model_used="test",
            reason="test reason",
        )
        prior = _pr(_pr_id(), _sha("old111")).add_review(
            prior_review,
            _sha("old111"),
        )
        reclassified = ReviewItem(
            id="shared-1",
            severity=ItemSeverity.MINOR,
            category=IssueCategory.BUG,
            file_path="src/app.py",
            description="Handle the failure path",
        )
        current_review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            items=[reclassified],
            summary="Needs changes",
            model_used="test",
            reason="test reason",
        )
        cmd = _cmd(pr_id=prior.id, sha=_sha("new222"))
        mock_pr_repository.find.return_value = prior
        mock_changeset_fetcher.fetch.return_value = _diff_fixture(
            cmd.pr_id,
            cmd.head_sha,
        )
        mock_llm_review.review_prompt.return_value = current_review

        ReviewPullRequestService(
            mock_pr_repository,
            mock_changeset_fetcher,
            mock_review_context_factory,
            mock_llm_review,
            mock_review_publisher,
        ).execute(cmd)

        published = mock_review_publisher.publish.call_args.args[1]

        assert [item.id for item in published.items] == ["shared-1"]
        assert published.suggestions == []
