from __future__ import annotations

from .types import PepEntry, _TYPE_PRIORITY

class PepRanker:
    def score(self, pep: PepEntry, target: tuple[int, int]) -> int:
        result = 0
        pep_type = (pep.get("type") or "").strip()
        pep_version = pep.get("python_version")

        result += _TYPE_PRIORITY.get(pep_type, 0)

        if pep_version is not None:
            for part in pep_version.split(","):
                part = part.strip()
                try:
                    ver = self._parse_version(part)
                except (ValueError, TypeError):
                    continue
                if ver <= target and target[1] - ver[1] <= 2:
                    result += 2
                    break

        return result

    def _parse_version(self, raw: str) -> tuple[int, int]:
        parts = raw.strip().split(".")
        if len(parts) < 2:
            raise ValueError(f"Not a valid version: {raw!r}")
        return int(parts[0]), int(parts[1])
