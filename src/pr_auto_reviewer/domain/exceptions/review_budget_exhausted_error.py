"""ReviewBudgetExhaustedError — the review hit its conversation budget."""


class ReviewBudgetExhaustedError(Exception):
    """Raised when a review would start a conversation beyond its budget.

    The budget caps the total number of peer conversations across all
    phases, feedback rounds, and retries of one review, so a
    non-converging model degrades to the best partial result instead of
    running for hours.
    """
