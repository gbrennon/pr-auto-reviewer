"""Tests for TokenDefaults."""

import pytest

from pr_auto_reviewer.infrastructure.client.token_defaults import TokenDefaults


class TestTokenDefaults:
    def test_all_empty_by_default(self):
        d = TokenDefaults()
        assert d.owner_token == ""
        assert d.reviewer_token == ""
        assert d.reviewer_username == ""

    def test_is_frozen_dataclass(self):
        d = TokenDefaults(owner_token="t")
        with pytest.raises(Exception):
            d.owner_token = "new"  # type: ignore[misc]

    def test_accepts_custom_values(self):
        d = TokenDefaults(
            owner_token="abc",
            reviewer_token="def",
            reviewer_username="ghi",
        )
        assert d.owner_token == "abc"
        assert d.reviewer_token == "def"
        assert d.reviewer_username == "ghi"
