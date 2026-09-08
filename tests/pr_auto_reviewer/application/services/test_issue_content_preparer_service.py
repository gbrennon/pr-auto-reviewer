"""Application-layer tests for IssueContentPreparerService."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pr_auto_reviewer.application.serializers.issue_body_builder import (
    IssueBodyBuilder,
)
from pr_auto_reviewer.application.services.issue_content_preparer_service import (
    IssueContentPreparerService,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.messages.commands.prepare_issue_content_command import (
    PrepareIssueContentCommand,
)
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId


class TestIssueContentPreparerService:

    def test_prepares_content_from_valid_json_response(
        self, _pr_id: PullRequestId, _item: ReviewItem
    ) -> None:
        mock_chat_port = MagicMock()
        mock_chat_port.send.return_value = (
            '{"title": "Decouple Service", "body": "## Problem\\nTight coupling\\n\\n## Rationale\\nTestability\\n\\n## Acceptance Criteria\\n- Port created"}'
        )

        service = IssueContentPreparerService(
            chat_port=mock_chat_port,
            issue_body_builder=IssueBodyBuilder(),
        )

        content = service.execute(
            PrepareIssueContentCommand(pr_id=_pr_id, item=_item)
        )

        assert content.title == "Decouple Service"
        assert "## Problem" in content.body
        assert "## Acceptance Criteria" in content.body
        mock_chat_port.send.assert_called_once()

    def test_prepares_content_from_markdown_fenced_json(
        self, _pr_id: PullRequestId, _item: ReviewItem
    ) -> None:
        mock_chat_port = MagicMock()
        mock_chat_port.send.return_value = (
            "Here is the issue:\n```json\n"
            '{"title": "Fenced Title", "body": "## Problem\\nFenced Body"}\n'
            "```\nHope this helps!"
        )

        service = IssueContentPreparerService(
            chat_port=mock_chat_port,
            issue_body_builder=IssueBodyBuilder(),
        )

        content = service.execute(
            PrepareIssueContentCommand(pr_id=_pr_id, item=_item)
        )

        assert content.title == "Fenced Title"
        assert content.body == "## Problem\nFenced Body"

    def test_falls_back_on_empty_response(
        self, _pr_id: PullRequestId, _item: ReviewItem
    ) -> None:
        mock_chat_port = MagicMock()
        mock_chat_port.send.return_value = ""

        service = IssueContentPreparerService(
            chat_port=mock_chat_port,
            issue_body_builder=IssueBodyBuilder(),
        )

        content = service.execute(
            PrepareIssueContentCommand(pr_id=_pr_id, item=_item)
        )

        assert content.title.startswith("[MAJOR] bug:")
        assert "Null check missing" in content.body

    def test_falls_back_on_unparseable_prose(
        self, _pr_id: PullRequestId, _item: ReviewItem
    ) -> None:
        mock_chat_port = MagicMock()
        mock_chat_port.send.return_value = "Sorry, I cannot format this as JSON."

        service = IssueContentPreparerService(
            chat_port=mock_chat_port,
            issue_body_builder=IssueBodyBuilder(),
        )

        content = service.execute(
            PrepareIssueContentCommand(pr_id=_pr_id, item=_item)
        )

        assert content.title.startswith("[MAJOR] bug:")
        assert "Null check missing" in content.body

    def test_falls_back_on_chat_port_exception(
        self, _pr_id: PullRequestId, _item: ReviewItem
    ) -> None:
        mock_chat_port = MagicMock()
        mock_chat_port.send.side_effect = RuntimeError("LLM connection timeout")

        service = IssueContentPreparerService(
            chat_port=mock_chat_port,
            issue_body_builder=IssueBodyBuilder(),
        )

        content = service.execute(
            PrepareIssueContentCommand(pr_id=_pr_id, item=_item)
        )

        assert content.title.startswith("[MAJOR] bug:")
        assert "Null check missing" in content.body

    def test_falls_back_on_empty_title_or_body(
        self, _pr_id: PullRequestId, _item: ReviewItem
    ) -> None:
        mock_chat_port = MagicMock()
        mock_chat_port.send.return_value = '{"title": "", "body": "   "}'

        service = IssueContentPreparerService(
            chat_port=mock_chat_port,
            issue_body_builder=IssueBodyBuilder(),
        )

        content = service.execute(
            PrepareIssueContentCommand(pr_id=_pr_id, item=_item)
        )

        assert content.title.startswith("[MAJOR] bug:")
        assert "Null check missing" in content.body

    def test_falls_back_on_non_dict_json(
        self, _pr_id: PullRequestId, _item: ReviewItem
    ) -> None:
        mock_chat_port = MagicMock()
        mock_chat_port.send.return_value = '["title", "body"]'

        service = IssueContentPreparerService(
            chat_port=mock_chat_port,
            issue_body_builder=IssueBodyBuilder(),
        )

        content = service.execute(
            PrepareIssueContentCommand(pr_id=_pr_id, item=_item)
        )

        assert content.title.startswith("[MAJOR] bug:")

    def test_handles_escaped_quotes_and_nested_braces_in_strings(
        self, _pr_id: PullRequestId, _item: ReviewItem
    ) -> None:
        mock_chat_port = MagicMock()
        mock_chat_port.send.return_value = (
            '{"title": "Handle \\"quotes\\" and {braces}", '
            '"body": "## Problem\\nNested {data} with \\"escapes\\""}'
        )

        service = IssueContentPreparerService(
            chat_port=mock_chat_port,
            issue_body_builder=IssueBodyBuilder(),
        )

        content = service.execute(
            PrepareIssueContentCommand(pr_id=_pr_id, item=_item)
        )

        assert content.title == 'Handle "quotes" and {braces}'
        assert 'Nested {data} with "escapes"' in content.body

    @pytest.fixture
    def _pr_id(self) -> PullRequestId:
        return PullRequestId(repository="owner/repo", number=42)

    @pytest.fixture
    def _item(self) -> ReviewItem:
        return ReviewItem(
            id="item-1",
            severity=ItemSeverity.MAJOR,
            category=IssueCategory.BUG,
            file_path="src/main.py",
            description="Null check missing",
        )
