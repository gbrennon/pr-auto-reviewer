from ._helpers import *


class TestReviewVerdict:
    """Verdict tests using stub ports — no MagicMock, no requests.post.

    The pipeline is:
      ReviewPullRequestService
        → review_context_factory.build()
        → llm_review.review_prompt(composed_prompt)
        → review_publisher.publish()
    """

    @pytest.fixture
    def pr_id(self) -> PullRequestId:
        return PullRequestId(repository="owner/repo", number=1)

    @pytest.fixture
    def head_sha(self) -> CommitSha:
        return CommitSha("abc123def456")

    @pytest.fixture
    def pr_id_fixture(self) -> PullRequestId:
        return PullRequestId(repository="owner/repo", number=1)

    @pytest.fixture
    def head_sha_fixture(self) -> CommitSha:
        return CommitSha("abc123def456")

    def test_shell_with_shebang_is_approved(
        self, pr_id: PullRequestId, head_sha: CommitSha,
    ) -> None:
        """Shell script WITH shebang → no issues → APPROVED."""
        diff = PullRequestDiff(
            pr_id=pr_id,
            head_sha=head_sha,
            diff_content=_load_fixture("diffs/shell-with-shebang.diff"),
            file_contents={
                "scripts/deploy.sh": _load_fixture("diffs/shell-with-shebang.full"),
            },
        )
        fetcher = FakeChangesetFetcher(diff)

        review = CodeReview(verdict=ReviewVerdict.APPROVED, model_used="code-review", reason="test reason", summary="test summary")
        llm_stub = FakeLlmReview(review)
        publisher = FakeReviewPublisher()
        ctx_factory = FakeReviewContextFactory()

        service = ReviewPullRequestService(
            pr_repository=FakePullRequestRepository(),
            changeset_fetcher=fetcher,
            review_context_factory=ctx_factory,
            llm_review=llm_stub,
            review_publisher=publisher,
        )
        service.execute(ReviewPullRequestCommand(
            pr_id=pr_id, head_sha=head_sha, title="Add deploy script",
        ))

        assert len(publisher.publish_calls) == 1
        published: CodeReview = publisher.publish_calls[0][1]
        assert published.verdict == ReviewVerdict.APPROVED
        assert published.model_used == "code-review"

    def test_shell_missing_shebang_real_model(
        self, pr_id: PullRequestId, head_sha: CommitSha,
    ) -> None:
        """Shell WITHOUT shebang — real model (code-review:latest) response."""
        diff = PullRequestDiff(
            pr_id=pr_id,
            head_sha=head_sha,
            diff_content=_load_fixture("diffs/shell-missing-shebang.diff"),
            file_contents={
                "scripts/deploy.sh": _load_fixture(
                    "diffs/shell-missing-shebang.full",
                ),
            },
        )
        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            model_used="code-review",
            items=[
                ReviewItem(id="id-1",
                    severity=ItemSeverity.MINOR,
                    category=IssueCategory.QUALITY,
                    file_path="scripts/deploy.sh",
                    description="Missing shebang in deploy script",
                ),
            ],
            reason="test reason",
            summary="test summary",
        )

        fetcher = FakeChangesetFetcher(diff)
        llm_stub = FakeLlmReview(review)
        publisher = FakeReviewPublisher()
        ctx_factory = FakeReviewContextFactory()

        service = ReviewPullRequestService(
            pr_repository=FakePullRequestRepository(),
            changeset_fetcher=fetcher,
            review_context_factory=ctx_factory,
            llm_review=llm_stub,
            review_publisher=publisher,
        )
        service.execute(ReviewPullRequestCommand(
            pr_id=pr_id, head_sha=head_sha, title="Add deploy script",
        ))

        assert len(publisher.publish_calls) == 1
        published: CodeReview = publisher.publish_calls[0][1]
        assert published.verdict == ReviewVerdict.APPROVED
        assert len(published.items) == 1

    def test_prompt_includes_file_content_in_composed_prompt(
        self, pr_id: PullRequestId, head_sha: CommitSha,
    ) -> None:
        """The ComposedPrompt passed to the LLM includes file contents."""
        diff = PullRequestDiff(
            pr_id=pr_id,
            head_sha=head_sha,
            diff_content=_load_fixture("diffs/shell-with-shebang.diff"),
            file_contents={
                "scripts/deploy.sh": _load_fixture("diffs/shell-with-shebang.full"),
            },
        )
        review = CodeReview(verdict=ReviewVerdict.APPROVED, model_used="code-review", reason="test reason", summary="test summary")

        fetcher = FakeChangesetFetcher(diff)
        llm_stub = FakeLlmReview(review)
        publisher = FakeReviewPublisher()
        expected_prompt = ComposedPrompt(
            content="You are a code reviewer.\n\n"
                    "## Full File Contents\n"
                    "### scripts/deploy.sh\n"
                    "#!/usr/bin/env bash\n"
                    "echo 'deploying...'\n",
            fragments_used=["solid"],
            total_tokens=50,
        )
        ctx_factory = FakeReviewContextFactory(prompt=expected_prompt)

        service = ReviewPullRequestService(
            pr_repository=FakePullRequestRepository(),
            changeset_fetcher=fetcher,
            review_context_factory=ctx_factory,
            llm_review=llm_stub,
            review_publisher=publisher,
        )
        service.execute(ReviewPullRequestCommand(
            pr_id=pr_id, head_sha=head_sha, title="Test prompt",
        ))

        assert len(llm_stub.review_prompt_calls) == 1
        prompt_sent: ComposedPrompt = llm_stub.review_prompt_calls[0]
        assert isinstance(prompt_sent, ComposedPrompt)
        assert "## Full File Contents" in prompt_sent.content
        assert "### scripts/deploy.sh" in prompt_sent.content
        assert "#!/usr/bin/env bash" in prompt_sent.content

    def test_verdict_follows_severity_rules(
        self, pr_id: PullRequestId, head_sha: CommitSha,
    ) -> None:
        """APPROVED vs CHANGES_REQUESTED driven by CodeReview objects."""
        diff = PullRequestDiff(
            pr_id=pr_id, head_sha=head_sha, diff_content="+new line",
        )
        fetcher = FakeChangesetFetcher(diff)
        ctx_factory = FakeReviewContextFactory()

        publisher1 = FakeReviewPublisher()
        approved_review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            summary="Minor issues only",
            model_used="code-review",
            reason="test reason",
        )
        llm_stub1 = FakeLlmReview(approved_review)

        service1 = ReviewPullRequestService(
            pr_repository=FakePullRequestRepository(),
            changeset_fetcher=fetcher,
            review_context_factory=ctx_factory,
            llm_review=llm_stub1,
            review_publisher=publisher1,
        )
        service1.execute(ReviewPullRequestCommand(
            pr_id=pr_id, head_sha=head_sha, title="info only",
        ))
        published1: CodeReview = publisher1.publish_calls[0][1]
        assert published1.verdict == ReviewVerdict.APPROVED

        publisher2 = FakeReviewPublisher()
        cr_review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            summary="Critical found",
            model_used="code-review",
            reason="test reason",
        )
        llm_stub2 = FakeLlmReview(cr_review)

        service2 = ReviewPullRequestService(
            pr_repository=FakePullRequestRepository(),
            changeset_fetcher=fetcher,
            review_context_factory=ctx_factory,
            llm_review=llm_stub2,
            review_publisher=publisher2,
        )
        service2.execute(ReviewPullRequestCommand(
            pr_id=pr_id, head_sha=head_sha, title="critical",
        ))
        published2 = publisher2.publish_calls[0][1]
        assert published2.verdict == ReviewVerdict.CHANGES_REQUESTED


    @pytest.mark.parametrize(
        "platform,pr_id,cli_args",
        [
            ("forgejo", "gbrennon/dotfiles", ["-r", "forgejo:gbrennon/dotfiles", "-p", "63"]),
            ("github", "gbrennon/ratatui", ["-r", "github:ratatui/ratatui", "-p", "1"]),
        ],
    )
    def test_e2e_review_terminal(
        self,
        platform: str,
        pr_id: str,
        cli_args: list[str],
        pr_id_fixture: PullRequestId,
        head_sha_fixture: CommitSha,
    ) -> None:
        """E2E review flow with terminal output for specific PRs.

        Uses ``review_output = terminal`` and the appropriate platform CLI args.
        """
        diff = PullRequestDiff(
            pr_id=pr_id_fixture,
            head_sha=head_sha_fixture,
            diff_content=_load_fixture("diffs/sample-service.diff"),
        )
        fetcher = FakeChangesetFetcher(diff)

        review = CodeReview(
            verdict=ReviewVerdict.APPROVED,
            summary="Good changes, approved",
            model_used="code-review",
            reason="test reason",
        )
        llm_stub = FakeLlmReview(review)
        publisher = FakeReviewPublisher()
        ctx_factory = FakeReviewContextFactory()

        service = ReviewPullRequestService(
            pr_repository=FakePullRequestRepository(),
            changeset_fetcher=fetcher,
            review_context_factory=ctx_factory,
            llm_review=llm_stub,
            review_publisher=publisher,
        )
        service.execute(ReviewPullRequestCommand(
            pr_id=pr_id_fixture, head_sha=head_sha_fixture, title="Review",
        ))

        assert len(publisher.publish_calls) == 1
        published: CodeReview = publisher.publish_calls[0][1]
        assert published.verdict == ReviewVerdict.APPROVED
        assert published.model_used == "code-review"
        assert len(published.items) == 0  # Clean review → no items

    def test_e2e_review_terminal_with_items(
        self,
        pr_id_fixture: PullRequestId,
        head_sha_fixture: CommitSha,
    ) -> None:
        """E2E review with items appearing in terminal output."""
        diff = PullRequestDiff(
            pr_id=pr_id_fixture,
            head_sha=head_sha_fixture,
            diff_content=_load_fixture("diffs/shell-missing-shebang.diff"),
            file_contents={
                "scripts/deploy.sh": _load_fixture(
                    "diffs/shell-missing-shebang.full",
                ),
            },
        )
        fetcher = FakeChangesetFetcher(diff)

        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            summary="Missing shebang detected",
            model_used="code-review",
            items=[
                ReviewItem(
                    id="id-1",
                    severity=ItemSeverity.MINOR,
                    category=IssueCategory.QUALITY,
                    file_path="scripts/deploy.sh",
                    description="Missing shebang in deploy script",
                ),
            ],
            reason="test reason",
        )
        llm_stub = FakeLlmReview(review)
        publisher = FakeReviewPublisher()
        ctx_factory = FakeReviewContextFactory()

        service = ReviewPullRequestService(
            pr_repository=FakePullRequestRepository(),
            changeset_fetcher=fetcher,
            review_context_factory=ctx_factory,
            llm_review=llm_stub,
            review_publisher=publisher,
        )
        service.execute(ReviewPullRequestCommand(
            pr_id=pr_id_fixture, head_sha=head_sha_fixture, title="Review",
        ))

        assert len(publisher.publish_calls) == 1
        published: CodeReview = publisher.publish_calls[0][1]
        assert published.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(published.items) == 1
        assert published.items[0].description == "Missing shebang in deploy script"

