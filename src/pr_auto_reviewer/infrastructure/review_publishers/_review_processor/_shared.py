"""Processor that extracts review-publication logic from platform adapters.

Pulls verdict mapping, item filtering, body formatting, and the
COMMENT-vs-formal decision into a single place so Forgejo and GitHub
publishers only carry platform-specific API details."""

from dataclasses import dataclass

from pr_auto_reviewer.application.ports.outbound.verdict_event_mapper_port import (
    VerdictEventMapperPort,
)
from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
from pr_auto_reviewer.domain.value_objects.pull_request_id import PullRequestId
from pr_auto_reviewer.domain.value_objects.review_verdict import ReviewVerdict
from pr_auto_reviewer.infrastructure.review_publishers.body_formatter import (
    ReviewBodyRenderer,
)
from pr_auto_reviewer.infrastructure.review_publishers.reason_factory import (
    ReasonFactory,
)

__all__ = ['CodeReview', 'PullRequestId', 'ReasonFactory', 'ReviewBodyRenderer', 'ReviewItem', 'ReviewVerdict', 'VerdictEventMapperPort', 'dataclass']
