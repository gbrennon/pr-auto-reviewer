"""Encryption helper for SQLite persistence."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from .encryption_key_error import EncryptionKeyError


class SqliteCipher:
    """Encrypt and decrypt application data with a caller-provided key."""

    def __init__(self, key: str) -> None:
        if not key:
            raise ValueError("Encryption key must not be empty")
        digest = hashlib.sha256(key.encode("utf-8")).digest()
        self._fernet = Fernet(base64.urlsafe_b64encode(digest))

    def encrypt(self, value: str) -> bytes:
        """Return encrypted UTF-8 data."""
        return self._fernet.encrypt(value.encode("utf-8"))

    def decrypt(self, value: bytes) -> str:
        """Return decrypted UTF-8 data or fail closed."""
        try:
            return self._fernet.decrypt(value).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as exc:
            raise EncryptionKeyError(
                "Configured encryption key could not decrypt persisted data; "
                "verify the key or check for corrupted storage",
            ) from exc
