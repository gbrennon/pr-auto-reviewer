from typing import Protocol


# ruleid: python-application-ports-must-use-protocol
class BrokenOutboundPort:
    """A concrete outbound port contract is invalid."""


class ValidOutboundPort(Protocol):
    """A structural outbound port contract."""
