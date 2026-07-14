"""Raised when a per-org token fails preflight verification — invalid auth
or missing write scope."""

from .domain_error import DomainError


class PreflightVerificationError(DomainError):
    """Token preflight check failed.

    Attributes:
        platform: ``"github"`` or ``"forgejo"``.
        org: Organisation the token was resolved for.
        role: ``"owner"`` or ``"reviewer"``.
        http_status: HTTP status code (401 or 403).
        step: Which check failed — ``"auth"`` or ``"write_access"``.
    """

    def __init__(
        self,
        platform: str,
        org: str,
        role: str,
        http_status: int,
        step: str,
    ) -> None:
        self.platform = platform
        self.org = org
        self.role = role
        self.http_status = http_status
        self.step = step
        super().__init__(self._build_message())

    def _build_message(self) -> str:
        hint = ""
        if self.step == "auth":
            hint = "Token is invalid or expired."
        elif self.http_status == 403:
            hint = "Token lacks write permission (needs 'Pull requests: Read and Write')."
        else:
            hint = "Token is invalid or expired."
        return (
            f"Preflight verification failed for {self.platform} org '{self.org}' "
            f"({self.role} token, HTTP {self.http_status} during {self.step}): {hint}"
        )
