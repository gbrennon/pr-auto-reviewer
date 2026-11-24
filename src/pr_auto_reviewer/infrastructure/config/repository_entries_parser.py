"""Normalize repository allow-list entries from persisted and legacy inputs."""

from __future__ import annotations

import json


class RepositoryEntriesParser:
    """Parse repository entries into immutable tuples or canonical lists."""

    def parse(self, raw: object) -> tuple[str, ...]:
        """Return normalized repository entries from supported input forms."""
        if raw is None:
            return ()
        if isinstance(raw, (list, tuple)):
            return self._parse_array(raw)
        if not isinstance(raw, str):
            raise ValueError("Repository entries must be a string, list, tuple, or None")
        stripped = raw.strip()
        if not stripped:
            return ()
        decoded = self._decode_json_array(stripped)
        if decoded is not None:
            return self._parse_array(decoded)
        return self._parse_legacy(stripped)

    def canonical_list(self, raw: object) -> list[str]:
        """Return normalized repository entries in persistence-friendly form."""
        return list(self.parse(raw))

    @staticmethod
    def _decode_json_array(raw: str) -> list[object] | None:
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return decoded if isinstance(decoded, list) else None

    @staticmethod
    def _parse_array(raw: list[object] | tuple[object, ...]) -> tuple[str, ...]:
        entries: list[str] = []
        for item in raw:
            if not isinstance(item, str):
                raise ValueError("Repository entries must be non-empty strings")
            entry = item.strip()
            if not entry:
                raise ValueError("Repository entries must be non-empty strings")
            entries.append(entry)
        return tuple(entries)

    @staticmethod
    def _parse_legacy(raw: str) -> tuple[str, ...]:
        normalized = raw.replace("\\n", "\n").replace("\r\n", "\n").replace("\r", "\n")
        return tuple(
            entry.strip()
            for entry in normalized.replace("\n", ",").split(",")
            if entry.strip()
        )
