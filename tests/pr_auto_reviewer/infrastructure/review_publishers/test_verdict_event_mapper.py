"""Tests for the per-host verdict-to-event mappers."""

from typing import cast

from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.review_publishers.forgejo_verdict_event_mapper import (
    ForgejoVerdictEventMapper,
)
from pr_auto_reviewer.infrastructure.review_publishers.github_verdict_event_mapper import (
    GithubVerdictEventMapper,
)


class TestGithubVerdictEventMapper:
    """Behaviour of GithubVerdictEventMapper.map(verdict) -> str."""

    def test_map_approve_verdict_is_approve(self) -> None:
        mapper = GithubVerdictEventMapper()
        assert mapper.map(ReviewVerdict.APPROVED) == "APPROVE"

    def test_map_changes_requested_is_request_changes(self) -> None:
        mapper = GithubVerdictEventMapper()
        assert mapper.map(ReviewVerdict.CHANGES_REQUESTED) == "REQUEST_CHANGES"

    def test_map_commented_is_comment(self) -> None:
        mapper = GithubVerdictEventMapper()
        assert mapper.map(ReviewVerdict.COMMENTED) == "COMMENT"

    def test_map_unknown_verdict_falls_back_to_comment(self) -> None:
        mapper = GithubVerdictEventMapper()
        assert mapper.map(cast(ReviewVerdict, "UNKNOWN")) == "COMMENT"


class TestForgejoVerdictEventMapper:
    """Behaviour of ForgejoVerdictEventMapper.map(verdict) -> str."""

    def test_map_approve_verdict_is_approved(self) -> None:
        mapper = ForgejoVerdictEventMapper()
        assert mapper.map(ReviewVerdict.APPROVED) == "APPROVED"

    def test_map_changes_requested_is_request_changes(self) -> None:
        mapper = ForgejoVerdictEventMapper()
        assert mapper.map(ReviewVerdict.CHANGES_REQUESTED) == "REQUEST_CHANGES"

    def test_map_commented_is_comment(self) -> None:
        mapper = ForgejoVerdictEventMapper()
        assert mapper.map(ReviewVerdict.COMMENTED) == "COMMENT"

    def test_map_unknown_verdict_falls_back_to_comment(self) -> None:
        mapper = ForgejoVerdictEventMapper()
        assert mapper.map(cast(ReviewVerdict, "UNKNOWN")) == "COMMENT"