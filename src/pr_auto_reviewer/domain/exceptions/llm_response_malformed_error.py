"""Raised when the LLM response cannot be parsed into a CodeReview."""

from .domain_error import DomainError


class LlmResponseMalformedError(DomainError):
    """Raised when the LLM response cannot be parsed into a CodeReview."""

    def __init__(self, raw_text: str) -> None:
        self.raw_text = raw_text
        super().__init__("LLM response could not be parsed into a structured review.")
