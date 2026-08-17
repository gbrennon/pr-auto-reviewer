from __future__ import annotations


class PepMatcher:
    def applies(self, pep_version: str | None, target: tuple[int, int]) -> bool:
        if pep_version is None:
            return True
        for part in pep_version.split(","):
            part = part.strip()
            try:
                ver = self.parse_version(part)
            except (ValueError, TypeError):
                continue
            if ver <= target:
                return True
        return False

    def parse_version(self, raw: str) -> tuple[int, int]:
        parts = raw.strip().split(".")
        if len(parts) < 2:
            raise ValueError(f"Not a valid version: {raw!r}")
        return int(parts[0]), int(parts[1])
