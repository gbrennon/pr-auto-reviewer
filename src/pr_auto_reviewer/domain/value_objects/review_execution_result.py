from dataclasses import dataclass


@dataclass(frozen=True)
class ReviewExecutionResult:
    """Describe whether a review ran and how long its review phase took."""
    duration_seconds: float | None

    reviewed: bool

    def __post_init__(self) -> None:
        """Require duration to exist exactly when a review was published."""
        if self.reviewed and self.duration_seconds is None:
            raise ValueError("A completed review requires a duration")
        if not self.reviewed and self.duration_seconds is not None:
            raise ValueError("A skipped review cannot have a duration")
        if self.duration_seconds is not None and self.duration_seconds < 0:
            raise ValueError("Review duration cannot be negative")
