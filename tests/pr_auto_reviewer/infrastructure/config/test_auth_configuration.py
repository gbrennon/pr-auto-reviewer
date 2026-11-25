"""Tests for global and repository authentication assignments."""

import pytest

from pr_auto_reviewer.infrastructure.config.auth_configuration import (
    AuthConfiguration,
    AuthConfigParser,
)


class TestAuthConfigParser:
    def test_parses_profiles_and_global_assignments(self) -> None:
        configuration = AuthConfigParser().parse(
            {
                "auth": {
                    "defaults": {
                        "manager_profile": "work-manager",
                        "reviewer_profile": "review-bot",
                    },
                    "profiles": {
                        "work-manager": {
                            "provider": "gh",
                            "host": "github.com",
                            "account": "alice",
                            "transport": "cli",
                        },
                        "review-bot": {
                            "provider": "gh",
                            "host": "github.com",
                            "account": "acme-reviewer",
                            "transport": "http",
                        },
                    },
                },
            }
        )

        assert configuration.defaults.manager_profile == "work-manager"
        assert configuration.defaults.reviewer_profile == "review-bot"
        assert configuration.profile("review-bot").transport == "http"

    def test_repository_assignment_overrides_global_assignment(self) -> None:
        configuration = AuthConfigParser().parse(
            {
                "auth": {
                    "defaults": {
                        "manager_profile": "global-manager",
                        "reviewer_profile": "global-reviewer",
                    },
                    "profiles": {},
                },
                "repositories": {
                    "codeberg.org/acme/project": {
                        "manager_profile": "repo-manager",
                        "reviewer_profile": "repo-reviewer",
                    }
                },
            }
        )

        assignments = configuration.for_repository("codeberg.org/acme/project")

        assert assignments.manager_profile == "repo-manager"
        assert assignments.reviewer_profile == "repo-reviewer"

    def test_global_assignment_is_used_when_repository_has_no_override(self) -> None:
        configuration = AuthConfigParser().parse(
            {
                "auth": {
                    "defaults": {
                        "manager_profile": "global-manager",
                        "reviewer_profile": "global-reviewer",
                    }
                }
            }
        )

        assignments = configuration.for_repository("github.com/acme/project")

        assert assignments.manager_profile == "global-manager"
        assert assignments.reviewer_profile == "global-reviewer"

    def test_unknown_profile_is_rejected(self) -> None:
        configuration = AuthConfiguration.empty()

        with pytest.raises(KeyError, match="missing"):
            configuration.profile("missing")
