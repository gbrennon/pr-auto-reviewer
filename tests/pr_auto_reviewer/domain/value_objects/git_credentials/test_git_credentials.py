"""Tests for the GitCredentials value object."""

from dataclasses import FrozenInstanceError

import pytest

from pr_auto_reviewer.domain.value_objects.git_credentials import GitCredentials


class TestGitCredentials:

    def test_is_frozen_and_carries_protocol_username_secret(self) -> None:
        creds = GitCredentials(protocol="https", username="alice", secret="s3cr3t")

        assert creds.protocol == "https"
        assert creds.username == "alice"
        assert creds.secret == "s3cr3t"
        with pytest.raises(FrozenInstanceError):
            creds.username = "mallory"

    def test_protocol_is_normalized_to_lowercase(self) -> None:
        creds = GitCredentials(protocol="SSH", username="alice")  # type: ignore[arg-type]

        assert creds.protocol == "ssh"

    def test_rejects_unsupported_protocol(self) -> None:
        with pytest.raises(ValueError, match="Unsupported clone protocol"):
            GitCredentials(protocol="ftp", username="alice")

    def test_accepts_clone_protocol_enum(self) -> None:
        from pr_auto_reviewer.domain.value_objects.clone_protocol import CloneProtocol

        creds = GitCredentials(protocol=CloneProtocol.SSH, username="alice", secret="")

        assert creds.protocol == "ssh"

    def test_rejects_empty_username(self) -> None:
        with pytest.raises(ValueError, match="username must not be empty"):
            GitCredentials(protocol="https", username="   ")
