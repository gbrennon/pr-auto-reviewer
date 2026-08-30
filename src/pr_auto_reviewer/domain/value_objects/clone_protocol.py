"""CloneProtocol - strategy enum for how repositories are cloned."""

from enum import Enum


class CloneProtocol(str, Enum):
    """Transport strategy used to clone and fetch a repository.

    Single source of truth for the clone protocol so the clone URL resolver
    and the credential prompt always agree on the same normalized value.
    """

    SSH = "ssh"
    HTTPS = "https"

    @classmethod
    def parse(cls, value: str | None) -> CloneProtocol:
        """Parse a raw config value into a canonical CloneProtocol.

        Accepts ``str`` or an existing ``CloneProtocol``; normalizes case and
        common aliases (``git`` -> ``ssh``, ``http`` -> ``https``). Raises
        ``ValueError`` for unsupported values so misconfiguration fails fast.
        """
        if isinstance(value, cls):
            return value
        normalized = (value or "").strip().lower()
        if normalized in ("ssh", "git"):
            return cls.SSH
        if normalized in ("https", "http"):
            return cls.HTTPS
        raise ValueError(f"Unsupported clone protocol: {value!r}")
