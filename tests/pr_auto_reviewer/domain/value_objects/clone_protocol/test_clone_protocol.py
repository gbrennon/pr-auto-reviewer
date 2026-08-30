"""Tests for the CloneProtocol strategy enum."""

import pytest

from pr_auto_reviewer.domain.value_objects.clone_protocol import CloneProtocol


class TestCloneProtocol:

    def test_parse_https_variants(self) -> None:
        for raw in ("https", "HTTPS", "http", "Http"):
            assert CloneProtocol.parse(raw) is CloneProtocol.HTTPS

    def test_parse_ssh_variants(self) -> None:
        for raw in ("ssh", "SSH", "git", "Git"):
            assert CloneProtocol.parse(raw) is CloneProtocol.SSH

    def test_parse_passthrough_of_enum(self) -> None:
        assert CloneProtocol.parse(CloneProtocol.SSH) is CloneProtocol.SSH

    def test_parse_rejects_unknown(self) -> None:
        for raw in ("ftp", "svn", "httpsgit"):
            with pytest.raises(ValueError, match="Unsupported clone protocol"):
                CloneProtocol.parse(raw)

    def test_values_are_canonical_strings(self) -> None:
        assert CloneProtocol.SSH.value == "ssh"
        assert CloneProtocol.HTTPS.value == "https"
