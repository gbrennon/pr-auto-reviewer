from typing import Protocol

from pr_auto_reviewer.application.dtos.show_status_request import ShowStatusRequest
from pr_auto_reviewer.application.dtos.show_status_response import ShowStatusResponse


class ShowStatusPort(Protocol):
    """Retrieve the current daemon status through one application operation."""

    def execute(self, request: ShowStatusRequest) -> ShowStatusResponse:
        """Return the current daemon status."""
        ...
