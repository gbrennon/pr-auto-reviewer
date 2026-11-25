from typing import Protocol

# ruleid: python-application-ports-must-use-protocol
class BrokenPort:
    """A fixture-only concrete port."""


class ValidPort(Protocol):
    """A structural port contract."""


class TranscriptMetadata:
    """A DTO with a non-port name."""
