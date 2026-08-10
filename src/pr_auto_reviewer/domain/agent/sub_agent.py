"""SubAgent — abstract contract every review sub-agent must satisfy."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Self, cast


class SubAgent(ABC):
    """Abstract contract for a specialized review sub-agent.

    A sub-agent is a role in the agentic review workflow with a defined
    responsibility and behavior. Concrete sub-agents implement the
    role-specific metadata; the workflow itself lives in the application
    layer, which composes sub-agents through ports.

    Instances are per-class singletons: every concrete sub-agent role
    is unique, so repeated instantiation returns the same object.
    """

    _instances: ClassVar[dict[type[SubAgent], SubAgent]] = {}

    def __new__(cls) -> Self:
        """Return the singleton instance for the concrete sub-agent class."""
        if cls not in cls._instances:
            cls._instances[cls] = super().__new__(cls)
        return cast(Self, cls._instances[cls])

    @property
    @abstractmethod
    def role(self) -> str:
        """Return the agent's role name."""

    @property
    @abstractmethod
    def responsibility(self) -> str:
        """Return the agent's responsibility statement."""

    @property
    @abstractmethod
    def behavior(self) -> str:
        """Return the agent's behavior description."""

    def describe(self) -> str:
        """Return a human-readable summary of the agent's role."""
        return f"{self.role}: {self.responsibility} — {self.behavior}"