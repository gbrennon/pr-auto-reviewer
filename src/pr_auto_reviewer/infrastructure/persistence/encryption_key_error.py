"""Errors raised when encrypted storage cannot be decrypted."""

from __future__ import annotations


class EncryptionKeyError(ValueError):
    """The configured key could not decrypt persisted encrypted data."""
