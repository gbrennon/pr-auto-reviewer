"""ConversationPurpose — explicit isolation boundaries for LLM requests."""

from enum import StrEnum


class ConversationPurpose(StrEnum):
    """Identify the independent context owned by an LLM request."""

    REVIEWER_PHASE = "reviewer_phase"
    ENGINEER_PHASE = "engineer_phase"
    ARCHITECT_PHASE = "architect_phase"
    ADVISOR_TURN = "advisor_turn"
    ADVISOR_PHASE = "advisor_phase"
    MANAGER_BRIEF = "manager_brief"
    FINDING_VERIFIER = "finding_verifier"
    ISSUE_CONTENT = "issue_content"
