"""Typed streaming response fake for chat-client tests."""

from collections.abc import Iterator


class FakeStreamingResponse:
    """Provide the response surface consumed by the streaming chat client."""

    def raise_for_status(self) -> None:
        """Represent a successful HTTP response."""

    def iter_lines(self, **_kwargs: object) -> Iterator[str]:
        """Yield one terminal server-sent event."""
        yield "data: [DONE]"
