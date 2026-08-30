"""GitCredentials - domain value object for git authentication."""

from dataclasses import dataclass

from pr_auto_reviewer.domain.value_objects.clone_protocol import CloneProtocol


@dataclass(frozen=True)
class GitCredentials:
    """Authentication data used to clone and fetch from a git host.

    Carries the clone protocol strategy, the account username, and the secret
    (password or token) used to authenticate. The protocol is stored as the
    canonical ``CloneProtocol`` enum so every consumer reads the same value.
    """

    protocol: CloneProtocol | str
    username: str
    secret: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.protocol, CloneProtocol):
            object.__setattr__(self, "protocol", CloneProtocol.parse(self.protocol))
        if not self.username.strip():
            raise ValueError("GitCredentials username must not be empty")
