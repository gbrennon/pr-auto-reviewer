"""E2E test for the ``review`` CLI command.

Runs the real ``review`` command against the real application service and
the real terminal publisher, backed entirely by fakes so no request ever
reaches GitHub, Codeberg, or an LLM.  The JSON block printed at the end of
the command must carry every attribute filled — no default or empty values.
"""

import json
from contextlib import redirect_stdout
from io import StringIO
from typing import ClassVar
from unittest.mock import MagicMock

from pr_auto_reviewer.application.ports.outbound.changeset_fetcher_port import (
    ChangesetFetcherPort,
)
from pr_auto_reviewer.application.ports.outbound.llm_review_port import LlmReviewPort
from pr_auto_reviewer.application.ports.outbound.pull_request_repository import (
    PullRequestRepository,
)
from pr_auto_reviewer.application.ports.outbound.review_context_factory_port import (
    ReviewContextFactoryPort,
)
from pr_auto_reviewer.application.services.review_pull_request_service import (
    ReviewPullRequestService,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.entities.review_praise import ReviewPraise
from pr_auto_reviewer.domain.entities.review_suggestion import ReviewSuggestion
from pr_auto_reviewer.domain.fragments.entities.composed_prompt import ComposedPrompt
from pr_auto_reviewer.domain.services.review_item_parser import ReviewItemParser
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.review_publishers.terminal_publisher import (
    TerminalReviewPublisherAdapter,
)
from pr_auto_reviewer.presentation.cli.runner import CliRunner
from pr_auto_reviewer.presentation.ports import OpenPullRequest, PrListerPort
from tests.fakes.fake_review_body_renderer_factory import FakeReviewBodyRendererFactory


_BODY = FakeReviewBodyRendererFactory.make()

_DIFF_TEXT = (
    "diff --git a/src/network.py b/src/network.py\n"
    "index 0000000..1111111 100644\n"
    "--- a/src/network.py\n"
    "+++ b/src/network.py\n"
    "@@ -0,0 +1,10 @@\n"
    "+import requests\n"
    "+\n"
    "+\n"
    "+def fetch_page(url):\n"
    "+    response = requests.get(url)\n"
    "+    return response.text\n"
)

_FILE_CONTENTS = {
    "src/network.py": (
        "import requests\n"
        "\n"
        "\n"
        "def fetch_page(url):\n"
        "    response = requests.get(url)\n"
        "    return response.text\n"
    )
}


class FakePrLister(PrListerPort):
    """PrListerPort fake that always returns one fixed open PR."""

    def __init__(self, open_pr: OpenPullRequest) -> None:
        self._open_pr = open_pr

    def list_open(self, repository: str) -> list[OpenPullRequest]:
        return [self._open_pr]

    def get_pr(self, repository: str, pr_number: int) -> OpenPullRequest | None:
        if self._open_pr.pr_id.number == pr_number:
            return self._open_pr
        return None


class FakePullRequestRepository(PullRequestRepository):
    """PullRequestRepository fake with no persisted history."""

    def __init__(self) -> None:
        self.saved: list = []

    def find(self, pr_id: PullRequestId) -> None:
        return None

    def save(self, pr) -> None:
        self.saved.append(pr)

    def reset(self) -> None:
        self.saved = []


class FakeChangesetFetcher(ChangesetFetcherPort):
    """ChangesetFetcherPort fake serving a fixed diff."""

    def __init__(self, diff: PullRequestDiff) -> None:
        self._diff = diff
        self.fetch_count = 0

    def fetch(self, pr_id: PullRequestId, sha: CommitSha) -> PullRequestDiff:
        self.fetch_count += 1
        return self._diff


class FakeReviewContextFactory(ReviewContextFactoryPort):
    """ReviewContextFactoryPort fake composing a deterministic prompt."""

    def build(
        self,
        pr_id: PullRequestId,
        diff: PullRequestDiff,
        pr_title: str | None = None,
        pr_description: str | None = None,
        target_branch: str = "",
    ) -> ComposedPrompt:
        return ComposedPrompt(
            content="You are a code reviewer.\n\n" + diff.diff_content,
            fragments_used=["solid", "python-errors"],
            total_tokens=512,
        )


class FakeLlmReview(LlmReviewPort):
    """LlmReviewPort fake returning a fully-populated CodeReview."""

    def __init__(self, review: CodeReview) -> None:
        self._review = review
        self.review_prompt_calls: list = []

    def review(self, diff: PullRequestDiff, context) -> CodeReview:
        return self._review

    def review_prompt(self, prompt) -> CodeReview:
        self.review_prompt_calls.append(prompt)
        return self._review


class TestReviewCliJsonOutput:
    """E2E: the ``review`` CLI command must emit a fully-populated JSON payload."""

    _TOP_LEVEL_KEYS: ClassVar[set[str]] = {
        "verdict",
        "reason",
        "summary",
        "items",
        "suggestions",
        "praise",
        "model_used",
    }
    _ITEM_KEYS: ClassVar[set[str]] = {
        "severity",
        "category",
        "file_path",
        "description",
        "line",
        "id",
        "current_code",
        "suggested_fix",
    }
    _SUGGESTION_KEYS: ClassVar[set[str]] = {
        "file",
        "line",
        "description",
        "current_code",
        "suggested_code",
    }
    _PRAISE_KEYS: ClassVar[set[str]] = {"file", "description"}

    @classmethod
    def _assert_no_defaults(cls, value) -> None:
        """Recursively assert every JSON value is non-empty."""
        if isinstance(value, dict):
            for key, val in value.items():
                assert val not in ("", None), (
                    f"JSON field {key!r} fell back to a default value {val!r}"
                )
                cls._assert_no_defaults(val)
        elif isinstance(value, list):
            for entry in value:
                cls._assert_no_defaults(entry)

    @staticmethod
    def _build_full_review() -> CodeReview:
        """Return the CodeReview a healthy LLM reply would produce."""
        return CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="Missing error handling and timeouts around network calls.",
            summary="Found 1 minor issue and 1 suggestion in the diff.",
            items=[
                ReviewItem(
                    severity=ItemSeverity.MINOR,
                    category=IssueCategory.MAINTAINABILITY,
                    file_path="src/network.py",
                    description="Prefer a context manager for network sessions.",
                    line="3-5",
                    id="ab12",
                    current_code="response = requests.get(url)",
                    suggested_fix=(
                        "with requests.get(url, timeout=10) as response:"
                    ),
                ),
            ],
            suggestions=[
                ReviewSuggestion(
                    file="src/network.py",
                    line="3",
                    description="Add an explicit timeout to every outbound request.",
                    current_code="response = requests.get(url)",
                    suggested_code="response = requests.get(url, timeout=10)",
                ),
            ],
            praise=[
                ReviewPraise(
                    file="src/network.py",
                    description="Small, focused helper that is easy to unit test.",
                ),
            ],
            model_used="code-review:latest",
        )

    @staticmethod
    def _build_runner(open_pr: OpenPullRequest, review: CodeReview) -> CliRunner:
        """Wire the real CLI runner against fake outbound adapters."""
        pr_id = open_pr.pr_id
        diff = PullRequestDiff(
            pr_id=pr_id,
            head_sha=open_pr.head_sha,
            diff_content=_DIFF_TEXT,
            file_contents=_FILE_CONTENTS,
            repository_structure="src/network.py",
            commit_messages=["Add fetch_page helper"],
            clone_path=None,
        )
        review_service = ReviewPullRequestService(
            pr_repository=FakePullRequestRepository(),
            changeset_fetcher=FakeChangesetFetcher(diff),
            review_context_factory=FakeReviewContextFactory(),
            llm_review=FakeLlmReview(review),
            review_publisher=TerminalReviewPublisherAdapter(
                body_renderer=_BODY,
                output_path=None,
            ),
        )
        return CliRunner(
            review_service=review_service,
            process_commands_service=MagicMock(),
            review_reader=MagicMock(),
            pr_lister=FakePrLister(open_pr),
            review_item_parser=ReviewItemParser(),
        )

    @staticmethod
    def _extract_json(output: str) -> dict:
        """Parse the JSON block printed after the ``--- JSON ---`` marker."""
        json_section = output.split("--- JSON ---", 1)[1]
        json_text = json_section.split("\n" + "=" * 60, 1)[0]
        return json.loads(json_text)

    def test_review_command_prints_json_with_all_fields_filled(self) -> None:
        pr_id = PullRequestId(repository="owner/repo", number=42)
        head_sha = CommitSha("a" * 40)
        open_pr = OpenPullRequest(
            pr_id=pr_id,
            head_sha=head_sha,
            title="Add network helper",
            description="Introduces a small fetch helper.",
            is_draft=False,
            target_branch="main",
        )
        runner = self._build_runner(open_pr, self._build_full_review())

        buffer = StringIO()
        with redirect_stdout(buffer):
            exit_code = runner._run_review(
                ["--repo", "owner/repo", "--pr", "42", "--force"]
            )

        assert exit_code == 0
        output = buffer.getvalue()
        assert "Review posted for PR #42" in output
        payload = self._extract_json(output)

        assert set(payload) == self._TOP_LEVEL_KEYS
        assert payload["verdict"] == "changes_requested"
        assert payload["reason"]
        assert payload["summary"]
        assert payload["model_used"] == "code-review:latest"
        assert payload["items"]
        assert payload["suggestions"]
        assert payload["praise"]

        item = payload["items"][0]
        assert set(item) == self._ITEM_KEYS
        assert item["id"] == "ab12"
        assert item["line"]
        assert item["current_code"]
        assert item["suggested_fix"]
        assert item["file_path"]

        suggestion = payload["suggestions"][0]
        assert set(suggestion) == self._SUGGESTION_KEYS
        assert suggestion["current_code"]
        assert suggestion["suggested_code"]
        assert suggestion["line"]

        praise = payload["praise"][0]
        assert set(praise) == self._PRAISE_KEYS
        assert praise["file"]

        self._assert_no_defaults(payload)

    @staticmethod
    def _extract_human_body(output: str) -> str:
        """Parse the human-readable block printed before the JSON marker."""
        human_section = output.split("--- HUMAN-READABLE ---", 1)[1]
        return human_section.split("--- JSON ---", 1)[0].strip()

    def test_review_command_shows_non_empty_item_id_in_body_and_json(self) -> None:
        """The review command output labels every item by a non-empty id, both
        in the human-readable body and in the JSON block."""
        import uuid as _uuid

        item_id = format(_uuid.uuid7().int, "04x")[:4]
        pr_id = PullRequestId(repository="owner/repo", number=42)
        head_sha = CommitSha("a" * 40)
        open_pr = OpenPullRequest(
            pr_id=pr_id,
            head_sha=head_sha,
            title="Add network helper",
            description="Introduces a small fetch helper.",
            is_draft=False,
            target_branch="main",
        )
        review = CodeReview(
            verdict=ReviewVerdict.CHANGES_REQUESTED,
            reason="Missing error handling.",
            summary="One issue found.",
            items=[
                ReviewItem(
                    severity=ItemSeverity.MINOR,
                    category=IssueCategory.MAINTAINABILITY,
                    file_path="src/network.py",
                    description="Prefer a context manager.",
                    line="3-5",
                    id=item_id,
                    current_code="response = requests.get(url)",
                    suggested_fix="with requests.get(url, timeout=10) as response:",
                )
            ],
            suggestions=[],
            praise=[],
            model_used="code-review:latest",
        )
        runner = self._build_runner(open_pr, review)

        buffer = StringIO()
        with redirect_stdout(buffer):
            exit_code = runner._run_review(
                ["--repo", "owner/repo", "--pr", "42", "--force"]
            )

        assert exit_code == 0
        output = buffer.getvalue()

        human_body = self._extract_human_body(output)
        assert f"\n{item_id}. [" in human_body

        payload = self._extract_json(output)
        assert payload["items"][0]["id"] == item_id
        assert payload["items"][0]["id"]