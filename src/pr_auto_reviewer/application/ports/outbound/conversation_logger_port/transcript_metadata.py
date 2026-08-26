from ._shared import *


class TranscriptMetadata:
    """The metadata keys every conversation logger understands.

    Event publishers and the logger share these spellings, so a key
    is declared once on the port contract instead of repeated as
    string literals across layers.
    """

    AGENT_ROLE = "agent_role"
    VERDICT = "verdict"
    ITEM_COUNT = "item_count"
    SKIPPED = "skipped"
    GRADE = "grade"
    FEEDBACK = "feedback"

