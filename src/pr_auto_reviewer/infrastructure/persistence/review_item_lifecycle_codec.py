"""JsonFilePullRequestRepository — persistence adapter for PullRequest aggregate.

Implements PullRequestRepositoryPort. Replaces the STATE_FILE bash script approach
with atomic writes and structured deserialization.
"""

from __future__ import annotations

import logging

from ...domain.value_objects.review_item_lifecycle import ReviewItemLifecycle
from ...domain.value_objects.review_item_status import ReviewItemStatus
from ...domain.value_objects.review_item_transition import ReviewItemTransition

logger = logging.getLogger(__name__)

_STATE_KEY_SEPARATOR = "/"


class ReviewItemLifecycleCodec:
    """Serialize and deserialize review-item lifecycle projections."""

    @staticmethod
    def serialize(lifecycle: ReviewItemLifecycle) -> dict:
        """Serialize a lifecycle projection into JSON-compatible data."""
        return {
            "item_id": lifecycle.item_id,
            "status": lifecycle.status.value,
            "first_seen_sha": lifecycle.first_seen_sha,
            "last_audited_sha": lifecycle.last_audited_sha,
            "status_explanation": lifecycle.status_explanation,
            "transitions": [
                {
                    "from_status": (
                        transition.from_status.value
                        if transition.from_status is not None
                        else None
                    ),
                    "to_status": transition.to_status.value,
                    "commit_sha": transition.commit_sha,
                    "explanation": transition.explanation,
                }
                for transition in lifecycle.transitions
            ],
        }

    @staticmethod
    def deserialize(raw_lifecycle: dict) -> ReviewItemLifecycle:
        """Deserialize a lifecycle projection from persisted JSON data."""
        transitions = tuple(
            ReviewItemTransition(
                from_status=(
                    ReviewItemStatus(raw_transition["from_status"])
                    if raw_transition.get("from_status") is not None
                    else None
                ),
                to_status=ReviewItemStatus(raw_transition["to_status"]),
                commit_sha=raw_transition.get("commit_sha", ""),
                explanation=raw_transition.get("explanation", ""),
            )
            for raw_transition in raw_lifecycle.get("transitions", [])
        )
        return ReviewItemLifecycle(
            item_id=raw_lifecycle.get("item_id", ""),
            status=ReviewItemStatus(raw_lifecycle.get("status", "created")),
            first_seen_sha=raw_lifecycle.get("first_seen_sha", ""),
            last_audited_sha=raw_lifecycle.get("last_audited_sha", ""),
            status_explanation=raw_lifecycle.get("status_explanation", ""),
            transitions=transitions,
        )

