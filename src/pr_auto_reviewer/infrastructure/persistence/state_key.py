"""JsonFilePullRequestRepository — persistence adapter for PullRequest aggregate.

Implements PullRequestRepositoryPort. Replaces the STATE_FILE bash script approach
with atomic writes and structured deserialization.
"""

from __future__ import annotations

import logging

from ...domain.value_objects.pull_request_id import PullRequestId

logger = logging.getLogger(__name__)

_STATE_KEY_SEPARATOR = "/"


class StateKey:
    """Build the composite storage key for a pull request."""

    @staticmethod
    def of(pr_id: PullRequestId) -> str:
        return f"{pr_id.repository}{_STATE_KEY_SEPARATOR}{pr_id.number}"

