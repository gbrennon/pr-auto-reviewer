"""Auto-discovered fixture pair tests — no code changes for new fixtures.

Capture a new pair:
    make capture-fixture REPO=... PR=... NAME=<name> REVIEW=1

This test automatically picks it up and validates all metadata.
"""

import json

import pytest

from pr_auto_reviewer.domain.value_objects.commit_sha import CommitSha
from pr_auto_reviewer.domain.value_objects.pull_request_diff import PullRequestDiff
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.repository_context import (
    RepositoryContext,
)
from pr_auto_reviewer.infrastructure.llm.prompt_builder import PromptBuilder
from tests.fixtures.auto_fixtures import discovered_pairs


class TestFixturePairs:
    """Auto-discovered tests for each captured fixture pair."""

    @pytest.mark.parametrize("fixture_pair", discovered_pairs(), indirect=True)
    def test_meta_has_required_fields(self, fixture_pair):
        """Every fixture has metadata: owner, repo, pr_number, head_sha."""
        meta = fixture_pair["meta"]
        assert meta["owner"], f"{fixture_pair['name']}: missing owner"
        assert meta["repo"], f"{fixture_pair['name']}: missing repo"
        assert meta["pr_number"] > 0, f"{fixture_pair['name']}: invalid pr_number"
        assert len(meta["head_sha"]) == 40, f"{fixture_pair['name']}: invalid head_sha"
        assert meta["title"], f"{fixture_pair['name']}: missing title"

    @pytest.mark.parametrize("fixture_pair", discovered_pairs(), indirect=True)
    def test_diff_is_readable(self, fixture_pair):
        """Every diff is non-empty and starts with diff header."""
        name = fixture_pair["name"]
        text = fixture_pair["diff_path"].read_text()
        assert len(text) > 100, f"{name}: diff too short"
        assert text.startswith("diff --git"), f"{name}: not a diff"

    @pytest.mark.parametrize("fixture_pair", discovered_pairs(), indirect=True)
    def test_diff_builds_prompt(self, fixture_pair):
        """Every diff builds an LLM prompt without error."""
        name = fixture_pair["name"]
        diff = PullRequestDiff(
            pr_id=None, head_sha=None,
            diff_content=fixture_pair["diff_path"].read_text(),
        )
        context = RepositoryContext(
            architecture_hint="test", repository_structure="", conventions=None,
        )
        prompt = PromptBuilder().build(diff, context)
        assert len(prompt) > len(diff.diff_content), f"{name}: prompt not built"

    @pytest.mark.parametrize("fixture_pair", discovered_pairs(), indirect=True)
    def test_review_is_valid(self, fixture_pair):
        """Every review (if present) has valid verdict, summary, items + metadata."""
        name = fixture_pair["name"]
        if fixture_pair["review_path"] is None:
            pytest.skip(f"{name}: no review")
        data = json.loads(fixture_pair["review_path"].read_text())
        if "_error" in data:
            pytest.skip(f"{name}: review generation failed")
        assert data["verdict"] in ("approved", "changes_requested", "commented")
        assert data["summary"], f"{name}: empty summary"
        assert isinstance(data["items"], list), f"{name}: items not a list"
        assert data.get("pr_number") is not None, f"{name}: missing pr_number in review"
        assert data.get("head_sha"), f"{name}: missing head_sha in review"

    @pytest.mark.parametrize("fixture_pair", discovered_pairs(), indirect=True)
    def test_meta_constructs_domain_objects(self, fixture_pair):
        """Metadata can construct PullRequestId and CommitSha without error."""
        meta = fixture_pair["meta"]
        pr_id = PullRequestId(
            repository=f"{meta['owner']}/{meta['repo']}",
            number=meta["pr_number"],
        )
        sha = CommitSha(meta["head_sha"])
        assert pr_id.repository == meta["full_repo"]
        assert sha.value == meta["head_sha"]
