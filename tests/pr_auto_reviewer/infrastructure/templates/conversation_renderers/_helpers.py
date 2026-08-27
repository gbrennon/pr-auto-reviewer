"""Shared helpers, fixtures, and imports for the split test modules."""

from __future__ import annotations

import jinja2
import pytest

from pr_auto_reviewer.infrastructure.templates.conversation_renderers import (
    AdvisorBlockMessageRenderer,
    AdvisorTurnGradeUserRenderer,
    EmptyResponseMessageRenderer,
    ExploreBeforeVerdictMessageRenderer,
    FeedbackContextRenderer,
    ForceVerdictMessageRenderer,
    InitialUserMessageRenderer,
    PhasePromptRenderer,
    RepeatedToolCallMessageRenderer,
    SuggestionsPraiseMessageRenderer,
    VerifyInitialUserRenderer,
)

__all__ = ['AdvisorBlockMessageRenderer', 'AdvisorTurnGradeUserRenderer', 'EmptyResponseMessageRenderer', 'ExploreBeforeVerdictMessageRenderer', 'FeedbackContextRenderer', 'ForceVerdictMessageRenderer', 'InitialUserMessageRenderer', 'PhasePromptRenderer', 'RepeatedToolCallMessageRenderer', 'SuggestionsPraiseMessageRenderer', 'VerifyInitialUserRenderer', 'annotations', 'jinja2', 'pytest']
