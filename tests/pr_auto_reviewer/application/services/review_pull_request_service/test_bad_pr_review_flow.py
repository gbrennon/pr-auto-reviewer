"""Integration and unit tests for bad PR review flows.

Verifies that pull requests containing real bugs, domain purity violations,
mutable domain objects, resource leaks, and unhandled exceptions are
accurately identified, validated against disk, and result in CHANGES_REQUESTED
verdicts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from pr_auto_reviewer.application.services.finding_aggregator_service import (
    FindingAggregatorService,
)
from pr_auto_reviewer.application.services.finding_verifier_service import (
    FindingVerifierService,
)
from pr_auto_reviewer.domain.messages.commands.aggregate_review_findings_command import (
    AggregateReviewFindingsCommand,
)
from pr_auto_reviewer.domain.messages.commands.verify_findings_command import (
    VerifyFindingsCommand,
)
from pr_auto_reviewer.domain.services.review_item_factory import (
    ReviewItemFactory,
)
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity
from pr_auto_reviewer.domain.value_objects.phase_result import PhaseResult
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.review_publishers.reason_factory import (
    ReasonFactory,
)


class _StubToolService:
    """Stub tool executor for verifier tests."""

    def execute(self, _action: str, _args: Any) -> dict[str, Any]:
        return {"status": "ok", "content": "file content"}


class TestBadPrReviewFlow:
    """Validate review pipeline accuracy and gating on bad pull requests."""

    @classmethod
    def _create_bad_repo(cls, tmp_path: Path) -> Path:
        """Populate a repository with intentional bugs and architecture violations."""
        repo_dir = tmp_path / "bad_repo"
        repo_dir.mkdir(parents=True, exist_ok=True)

        domain_dir = repo_dir / "src" / "pr_auto_reviewer" / "domain" / "entities"
        domain_dir.mkdir(parents=True, exist_ok=True)
        domain_file = domain_dir / "user_profile.py"
        domain_file.write_text(
            "from dataclasses import dataclass\n"
            "from pr_auto_reviewer.infrastructure.llm.ollama.ollama_chat_client import OllamaChatClient\n"
            "\n"
            "@dataclass\n"
            "class UserProfile:\n"
            "    user_id: str\n"
            "    roles: list[str]\n"
            "\n"
            "    def add_role(self, role: str) -> None:\n"
            "        self.roles.append(role)\n"
        )

        app_dir = repo_dir / "src" / "pr_auto_reviewer" / "application" / "services"
        app_dir.mkdir(parents=True, exist_ok=True)
        app_file = app_dir / "auth_service.py"
        app_file.write_text(
            "import os\n"
            "\n"
            "class AuthService:\n"
            "    def parse_token(self, token: str | None) -> str:\n"
            "        return token.strip().lower()\n"
            "\n"
            "    def dump_session(self, path: str, data: str) -> None:\n"
            "        f = open(path, 'w')\n"
            "        f.write(data)\n"
        )

        return repo_dir

    def test_review_when_bad_pr_has_domain_importing_infrastructure_then_requests_changes_with_blocking_item(
        self, tmp_path: Path,
    ) -> None:
        """Domain importing infrastructure is verified, survives gates, and triggers CHANGES_REQUESTED."""
        repo_dir = self._create_bad_repo(tmp_path)
        changed_files = ["src/pr_auto_reviewer/domain/entities/user_profile.py"]

        factory = ReviewItemFactory()
        raw_items = [
            {
                "file": "src/pr_auto_reviewer/domain/entities/user_profile.py",
                "line": "2",
                "severity": "critical",
                "category": "architecture",
                "description": "Domain layer must not import from Infrastructure layer.",
                "current_code": (
                    "from pr_auto_reviewer.infrastructure.llm.ollama.ollama_chat_client "
                    "import OllamaChatClient"
                ),
                "suggested_fix": (
                    "from pr_auto_reviewer.application.ports.outbound.agent_chat_port "
                    "import AgentChatPort"
                ),
            },
        ]
        items, skip_reasons = factory.create(raw_items, repo_dir, changed_files)
        assert len(items) == 1
        assert len(skip_reasons) == 0
        assert items[0].severity == ItemSeverity.CRITICAL

        mock_chat = MagicMock()
        mock_chat.send.side_effect = [
            json.dumps({"action": "read_file", "args": "src/pr_auto_reviewer/domain/entities/user_profile.py"}),
            json.dumps({
                "results": [
                    {
                        "finding_index": 0,
                        "verified": True,
                        "reasoning": "Confirmed forbidden infrastructure import inside domain entity.",
                    },
                ],
            }),
        ]

        verifier = FindingVerifierService(
            chat_port=mock_chat,
            verify_prompt="Verify these findings against {findings}",
            tool_factory=lambda _repo, _files, _sid: _StubToolService(),
        )
        verified_items = verifier.execute(
            VerifyFindingsCommand(
                items=items,
                repo_path=repo_dir,
                changed_files=changed_files,
                review_session="test-session",
            )
        )
        assert len(verified_items) == 1
        assert verified_items[0].severity == ItemSeverity.CRITICAL

        aggregator = FindingAggregatorService(reason_factory=ReasonFactory())
        phase_result = PhaseResult(
            items=verified_items,
            llm_verdict="changes_requested",
            llm_reason="Found critical architecture violations.",
            llm_summary="Domain layer boundaries were broken.",
        )
        review = aggregator.execute(
            AggregateReviewFindingsCommand(
                items=verified_items,
                model_used="code-review:latest",
                phase_result=phase_result,
            )
        )
        assert review.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(review.items) == 1
        assert review.items[0].category == IssueCategory.DESIGN

    def test_review_when_bad_pr_has_mutable_domain_entity_then_requests_changes(
        self, tmp_path: Path,
    ) -> None:
        """Unfrozen dataclass with in-place mutation is caught as major architecture issue."""
        repo_dir = self._create_bad_repo(tmp_path)
        changed_files = ["src/pr_auto_reviewer/domain/entities/user_profile.py"]

        factory = ReviewItemFactory()
        raw_items = [
            {
                "file": "src/pr_auto_reviewer/domain/entities/user_profile.py",
                "line": "4",
                "severity": "major",
                "category": "architecture",
                "description": "Domain entities must be frozen dataclasses to preserve immutability.",
                "current_code": (
                    "@dataclass\n"
                    "class UserProfile:\n"
                    "    user_id: str\n"
                    "    roles: list[str]"
                ),
                "suggested_fix": (
                    "@dataclass(frozen=True)\n"
                    "class UserProfile:\n"
                    "    user_id: str\n"
                    "    roles: tuple[str, ...]"
                ),
            },
        ]
        items, _ = factory.create(raw_items, repo_dir, changed_files)
        assert len(items) == 1
        assert items[0].severity == ItemSeverity.MAJOR

        mock_chat = MagicMock()
        mock_chat.send.side_effect = [
            json.dumps({"action": "read_file", "args": "src/pr_auto_reviewer/domain/entities/user_profile.py"}),
            json.dumps({
                "results": [
                    {
                        "finding_index": 0,
                        "verified": True,
                        "reasoning": "Confirmed un-frozen dataclass.",
                    },
                ],
            }),
        ]

        verifier = FindingVerifierService(
            chat_port=mock_chat,
            verify_prompt="Verify: {findings}",
            tool_factory=lambda _repo, _files, _sid: _StubToolService(),
        )
        verified_items = verifier.execute(
            VerifyFindingsCommand(
                items=items,
                repo_path=repo_dir,
                changed_files=changed_files,
                review_session="test-session",
            )
        )
        assert len(verified_items) == 1

        aggregator = FindingAggregatorService(reason_factory=ReasonFactory())
        phase_result = PhaseResult(
            items=verified_items,
            llm_verdict="changes_requested",
            llm_reason="Mutable domain entities violate immutability rules.",
            llm_summary="Found mutable domain entity.",
        )
        review = aggregator.execute(
            AggregateReviewFindingsCommand(
                items=verified_items,
                model_used="code-review:latest",
                phase_result=phase_result,
            )
        )
        assert review.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(review.items) == 1

    def test_review_when_bad_pr_has_unhandled_none_dereference_then_requests_changes(
        self, tmp_path: Path,
    ) -> None:
        """Missing None check causing possible AttributeError is verified as a critical bug."""
        repo_dir = self._create_bad_repo(tmp_path)
        changed_files = ["src/pr_auto_reviewer/application/services/auth_service.py"]

        factory = ReviewItemFactory()
        raw_items = [
            {
                "file": "src/pr_auto_reviewer/application/services/auth_service.py",
                "line": "4",
                "severity": "critical",
                "category": "bug",
                "description": "Calling .strip().lower() on optional token crashes with AttributeError when token is None.",
                "current_code": (
                    "    def parse_token(self, token: str | None) -> str:\n"
                    "        return token.strip().lower()"
                ),
                "suggested_fix": (
                    "    def parse_token(self, token: str | None) -> str:\n"
                    "        if not token:\n"
                    "            return ''\n"
                    "        return token.strip().lower()"
                ),
            },
        ]
        items, _ = factory.create(raw_items, repo_dir, changed_files)
        assert len(items) == 1
        assert items[0].severity == ItemSeverity.CRITICAL

        mock_chat = MagicMock()
        mock_chat.send.side_effect = [
            json.dumps({"action": "read_file", "args": "src/pr_auto_reviewer/application/services/auth_service.py"}),
            json.dumps({
                "results": [
                    {
                        "finding_index": 0,
                        "verified": True,
                        "reasoning": "Calling strip on None raises AttributeError at runtime.",
                    },
                ],
            }),
        ]

        verifier = FindingVerifierService(
            chat_port=mock_chat,
            verify_prompt="Verify: {findings}",
            tool_factory=lambda _repo, _files, _sid: _StubToolService(),
        )
        verified_items = verifier.execute(
            VerifyFindingsCommand(
                items=items,
                repo_path=repo_dir,
                changed_files=changed_files,
                review_session="test-session",
            )
        )
        assert len(verified_items) == 1

        aggregator = FindingAggregatorService(reason_factory=ReasonFactory())
        phase_result = PhaseResult(
            items=verified_items,
            llm_verdict="changes_requested",
            llm_reason="Found null dereference bug.",
            llm_summary="Critical logic bug present.",
        )
        review = aggregator.execute(
            AggregateReviewFindingsCommand(
                items=verified_items,
                model_used="code-review:latest",
                phase_result=phase_result,
            )
        )
        assert review.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(review.items) == 1
        assert review.items[0].category == IssueCategory.BUG

    def test_review_when_bad_pr_has_resource_leak_then_requests_changes(
        self, tmp_path: Path,
    ) -> None:
        """Unclosed file handle is verified as a major quality/resource issue."""
        repo_dir = self._create_bad_repo(tmp_path)
        changed_files = ["src/pr_auto_reviewer/application/services/auth_service.py"]

        factory = ReviewItemFactory()
        raw_items = [
            {
                "file": "src/pr_auto_reviewer/application/services/auth_service.py",
                "line": "7",
                "severity": "major",
                "category": "quality",
                "description": "File opened without context manager leaks file descriptor.",
                "current_code": (
                    "    def dump_session(self, path: str, data: str) -> None:\n"
                    "        f = open(path, 'w')\n"
                    "        f.write(data)"
                ),
                "suggested_fix": (
                    "    def dump_session(self, path: str, data: str) -> None:\n"
                    "        with open(path, 'w') as f:\n"
                    "            f.write(data)"
                ),
            },
        ]
        items, _ = factory.create(raw_items, repo_dir, changed_files)
        assert len(items) == 1

        mock_chat = MagicMock()
        mock_chat.send.side_effect = [
            json.dumps({"action": "read_file", "args": "src/pr_auto_reviewer/application/services/auth_service.py"}),
            json.dumps({
                "results": [
                    {
                        "finding_index": 0,
                        "verified": True,
                        "reasoning": "Missing with statement leaves file descriptor open.",
                    },
                ],
            }),
        ]

        verifier = FindingVerifierService(
            chat_port=mock_chat,
            verify_prompt="Verify: {findings}",
            tool_factory=lambda _repo, _files, _sid: _StubToolService(),
        )
        verified_items = verifier.execute(
            VerifyFindingsCommand(
                items=items,
                repo_path=repo_dir,
                changed_files=changed_files,
                review_session="test-session",
            )
        )
        assert len(verified_items) == 1

        aggregator = FindingAggregatorService(reason_factory=ReasonFactory())
        phase_result = PhaseResult(
            items=verified_items,
            llm_verdict="changes_requested",
            llm_reason="Found resource leak.",
            llm_summary="Major quality issues detected.",
        )
        review = aggregator.execute(
            AggregateReviewFindingsCommand(
                items=verified_items,
                model_used="code-review:latest",
                phase_result=phase_result,
            )
        )
        assert review.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(review.items) == 1

    def test_review_when_bad_pr_mixes_real_bugs_and_hallucinations_then_filters_fake_and_keeps_real(
        self, tmp_path: Path,
    ) -> None:
        """Gating cleanly drops hallucinated snippets while preserving real verified bugs."""
        repo_dir = self._create_bad_repo(tmp_path)
        changed_files = [
            "src/pr_auto_reviewer/domain/entities/user_profile.py",
            "src/pr_auto_reviewer/application/services/auth_service.py",
        ]

        factory = ReviewItemFactory()
        raw_items = [
            {
                "file": "src/pr_auto_reviewer/application/services/auth_service.py",
                "line": "4",
                "severity": "critical",
                "category": "bug",
                "description": "Real bug: None token dereference.",
                "current_code": (
                    "    def parse_token(self, token: str | None) -> str:\n"
                    "        return token.strip().lower()"
                ),
                "suggested_fix": (
                    "    def parse_token(self, token: str | None) -> str:\n"
                    "        return token.strip().lower() if token else ''"
                ),
            },
            {
                "file": "src/pr_auto_reviewer/application/services/auth_service.py",
                "line": "100",
                "severity": "critical",
                "category": "bug",
                "description": "Hallucination 1: Made-up snippet not in file.",
                "current_code": "def non_existent_method(self):\n    return self.unknown",
                "suggested_fix": "def non_existent_method(self):\n    return None",
            },
            {
                "file": "src/pr_auto_reviewer/domain/entities/user_profile.py",
                "line": "2",
                "severity": "critical",
                "category": "architecture",
                "description": "Real violation: forbidden infrastructure import.",
                "current_code": (
                    "from pr_auto_reviewer.infrastructure.llm.ollama.ollama_chat_client "
                    "import OllamaChatClient"
                ),
                "suggested_fix": "from pr_auto_reviewer.application.ports.outbound.agent_chat_port import AgentChatPort",
            },
            {
                "file": "src/pr_auto_reviewer/domain/entities/user_profile.py",
                "line": "4",
                "severity": "major",
                "category": "quality",
                "description": "Hallucination 2: No-op identical code and fix.",
                "current_code": "@dataclass\nclass UserProfile:",
                "suggested_fix": "@dataclass\nclass UserProfile:",
            },
        ]

        items, skip_reasons = factory.create(raw_items, repo_dir, changed_files)
        assert len(items) == 3
        assert len(skip_reasons) == 1

        mock_chat = MagicMock()
        mock_chat.send.side_effect = [
            json.dumps({"action": "read_file", "args": "src/pr_auto_reviewer/domain/entities/user_profile.py"}),
            json.dumps({
                "results": [
                    {
                        "finding_index": 0,
                        "verified": True,
                        "reasoning": "Real bug verified.",
                    },
                    {
                        "finding_index": 1,
                        "verified": True,
                        "reasoning": "Real architecture violation verified.",
                    },
                ],
            }),
        ]

        verifier = FindingVerifierService(
            chat_port=mock_chat,
            verify_prompt="Verify: {findings}",
            tool_factory=lambda _repo, _files, _sid: _StubToolService(),
        )
        verified_items = verifier.execute(
            VerifyFindingsCommand(
                items=items,
                repo_path=repo_dir,
                changed_files=changed_files,
                review_session="test-session",
            )
        )

        assert len(verified_items) == 2
        descriptions = [it.description for it in verified_items]
        assert "Real bug: None token dereference." in descriptions
        assert "Real violation: forbidden infrastructure import." in descriptions

        aggregator = FindingAggregatorService(reason_factory=ReasonFactory())
        phase_result = PhaseResult(
            items=verified_items,
            llm_verdict="changes_requested",
            llm_reason="Found 2 verified issues (2 hallucinations were dropped).",
            llm_summary="Critical issues present.",
        )
        review = aggregator.execute(
            AggregateReviewFindingsCommand(
                items=verified_items,
                model_used="code-review:latest",
                phase_result=phase_result,
            )
        )
        assert review.verdict == ReviewVerdict.CHANGES_REQUESTED
        assert len(review.items) == 2
