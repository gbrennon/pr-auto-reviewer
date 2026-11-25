"""Authentication profile and repository assignment configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from pr_auto_reviewer.infrastructure.config.auth_profile import AuthProfile


@dataclass(frozen=True)
class AuthAssignments:
    """Select the manager and reviewer profiles for a repository."""

    manager_profile: str = ""
    reviewer_profile: str = ""


@dataclass(frozen=True)
class AuthConfiguration:
    """Resolve authentication profiles from global and repository settings."""

    profiles: tuple[AuthProfile, ...]
    defaults: AuthAssignments
    repository_assignments: tuple[tuple[str, AuthAssignments], ...]

    @classmethod
    def empty(cls) -> AuthConfiguration:
        """Return an empty authentication configuration."""
        return cls((), AuthAssignments(), ())

    def profile(self, profile_id: str) -> AuthProfile:
        """Return a configured profile by ID."""
        for profile in self.profiles:
            if profile.profile_id == profile_id:
                return profile
        raise KeyError(f"Unknown authentication profile: {profile_id}")

    def for_repository(self, repository: str) -> AuthAssignments:
        """Return repository-specific assignments or global defaults."""
        for configured_repository, assignments in self.repository_assignments:
            if configured_repository == repository:
                return assignments
        return self.defaults


class AuthConfigParser:
    """Parse structured authentication settings from TOML values."""

    def parse(self, source: Mapping[str, object]) -> AuthConfiguration:
        """Parse profiles, defaults, and repository assignments."""
        auth = self._mapping(source.get("auth", {}))
        defaults = self._assignments(self._mapping(auth.get("defaults", {})))
        profiles = tuple(
            self._profile(profile_id, self._mapping(values))
            for profile_id, values in self._mapping(auth.get("profiles", {})).items()
        )
        repositories = tuple(
            (
                repository,
                self._assignments(self._mapping(values)),
            )
            for repository, values in self._mapping(source.get("repositories", {})).items()
            if self._has_auth_assignment(values)
        )
        return AuthConfiguration(profiles, defaults, repositories)

    def _profile(self, profile_id: str, values: Mapping[str, object]) -> AuthProfile:
        return AuthProfile(
            profile_id=profile_id,
            provider=self._required(values, "provider"),
            host=self._required(values, "host"),
            account=self._required(values, "account"),
            transport=self._required(values, "transport"),
        )

    def _assignments(self, values: Mapping[str, object]) -> AuthAssignments:
        return AuthAssignments(
            manager_profile=str(values.get("manager_profile", "")),
            reviewer_profile=str(values.get("reviewer_profile", "")),
        )

    def _has_auth_assignment(self, values: object) -> bool:
        if not isinstance(values, Mapping):
            return False
        return "manager_profile" in values or "reviewer_profile" in values

    def _required(self, values: Mapping[str, object], name: str) -> str:
        value = str(values.get(name, "")).strip()
        if not value:
            raise ValueError(f"Authentication profile requires {name}")
        return value

    def _mapping(self, value: object) -> Mapping[str, object]:
        if isinstance(value, Mapping):
            return value
        raise ValueError("Authentication settings must be TOML tables")
