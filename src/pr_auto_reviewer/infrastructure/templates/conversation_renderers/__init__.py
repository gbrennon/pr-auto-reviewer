"""Conversation renderer components — one renderer class per template.

Every conversation message in the review pipeline is a template
component: a ``.j2`` file under ``templates/conversation/`` holds the
prose (with any JSON contract spelled once in the shared schema macros),
and exactly one renderer class backs that template.  This package
mirrors the template tree: ``review_phase/``, ``advisor/``,
``manager/``, ``verifier/``, and ``orchestrator/``.
"""

from pr_auto_reviewer.infrastructure.templates.conversation_renderers.advisor import (
    AdvisorPhaseGradeSystemRenderer,
    AdvisorPhaseGradeUserRenderer,
    AdvisorTurnGradeSystemRenderer,
    AdvisorTurnGradeUserRenderer,
)
from pr_auto_reviewer.infrastructure.templates.conversation_renderers.issue_content import (
    IssueContentSystemRenderer,
    IssueContentUserRenderer,
)
from pr_auto_reviewer.infrastructure.templates.conversation_renderers.manager import (
    ManagerBriefSystemRenderer,
    ManagerBriefUserRenderer,
)
from pr_auto_reviewer.infrastructure.templates.conversation_renderers.orchestrator import (
    AdvisorCorrectionRenderer,
    FeedbackContextRenderer,
    PhasePromptRenderer,
)
from pr_auto_reviewer.infrastructure.templates.conversation_renderers.review_phase import (
    AdvisorBlockMessageRenderer,
    AdvisorFeedbackMessageRenderer,
    EmptyResponseMessageRenderer,
    ExploreBeforeVerdictMessageRenderer,
    ForceVerdictMessageRenderer,
    InitialUserMessageRenderer,
    RepeatedToolCallMessageRenderer,
    SuggestionsPraiseMessageRenderer,
    UnparseableResponseMessageRenderer,
)
from pr_auto_reviewer.infrastructure.templates.conversation_renderers.verifier import (
    ExploreBeforeResultsRenderer,
    VerifyEmptyResponseRenderer,
    VerifyInitialUserRenderer,
    VerifyUnparseableResponseRenderer,
)

__all__ = [
    "AdvisorBlockMessageRenderer",
    "AdvisorCorrectionRenderer",
    "AdvisorFeedbackMessageRenderer",
    "AdvisorPhaseGradeSystemRenderer",
    "AdvisorPhaseGradeUserRenderer",
    "AdvisorTurnGradeSystemRenderer",
    "AdvisorTurnGradeUserRenderer",
    "EmptyResponseMessageRenderer",
    "ExploreBeforeResultsRenderer",
    "ExploreBeforeVerdictMessageRenderer",
    "FeedbackContextRenderer",
    "ForceVerdictMessageRenderer",
    "InitialUserMessageRenderer",
    "IssueContentSystemRenderer",
    "IssueContentUserRenderer",
    "ManagerBriefSystemRenderer",
    "ManagerBriefUserRenderer",
    "PhasePromptRenderer",
    "RepeatedToolCallMessageRenderer",
    "SuggestionsPraiseMessageRenderer",
    "UnparseableResponseMessageRenderer",
    "VerifyEmptyResponseRenderer",
    "VerifyInitialUserRenderer",
    "VerifyUnparseableResponseRenderer",
]
