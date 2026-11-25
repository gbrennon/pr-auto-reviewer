"""Tests for configured authentication profiles."""

from pr_auto_reviewer.infrastructure.config.auth_profile import AuthProfile


class TestAuthProfile:
    def test_profile_describes_cli_identity(self) -> None:
        profile = AuthProfile(
            profile_id="work-manager",
            provider="gh",
            host="github.com",
            account="alice",
            transport="cli",
        )

        assert profile.profile_id == "work-manager"
        assert profile.provider == "gh"
        assert profile.host == "github.com"
        assert profile.account == "alice"
        assert profile.transport == "cli"
