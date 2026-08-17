from __future__ import annotations

from .types import _EXCLUDED_STATUSES, _EXCLUDED_TOPICS, PepEntry


class PepFilter:
    def is_relevant(self, pep: PepEntry) -> bool:
        topic = (pep.get("topic") or "").strip()
        status = (pep.get("status") or "").strip()
        pep_type = (pep.get("type") or "").strip()

        if not topic:
            return False
        if topic.lower() in _EXCLUDED_TOPICS:
            return False
        if status in _EXCLUDED_STATUSES:
            return False
        return not (pep_type == "Standards Track" and status != "Final")
