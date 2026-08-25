from ._shared import *


class ResponseFieldNormalizer:
    def normalize_issue(self, raw: dict[str, Any], index: int) -> dict[str, str]:
        file_path = self._ensure_str(raw.get("file"), f"file-{index}")
        description = self._coerce_description(raw.get("description") or raw.get("details"))
        severity = self._coerce_severity(raw.get("severity"))
        category = self._coerce_category(raw.get("category") or raw.get("type"))
        current_code = self._ensure_str(raw.get("current_code"))
        suggested_fix = self._ensure_str(raw.get("suggested_fix"))
        line = self._ensure_str(raw.get("line"))
        return {
            "file": file_path,
            "description": description,
            "severity": severity,
            "category": category,
            "current_code": current_code,
            "suggested_fix": suggested_fix,
            "line": line,
        }

    def normalize_summary(self, value: Any) -> str:
        return self._ensure_str(value)

    def normalize_verdict(self, value: Any) -> str:
        return self._ensure_str(value)

    def normalize_suggestions(self, raw: list[Any]) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for s in raw:
            if isinstance(s, dict):
                result.append({
                    "file": self._ensure_str(s.get("file")),
                    "line": self._ensure_str(s.get("line")),
                    "description": self._ensure_str(s.get("description")),
                    "current_code": self._ensure_str(s.get("current_code")),
                    "suggested_code": self._ensure_str(s.get("suggested_code")),
                })
        return result

    def normalize_praise(self, raw: list[Any]) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        for p in raw:
            if isinstance(p, dict):
                result.append({
                    "file": self._ensure_str(p.get("file")),
                    "description": self._ensure_str(p.get("description")),
                })
        return result

    def normalize_reason(self, value: Any) -> str:
        if isinstance(value, list):
            return " ".join(self._ensure_str(r) for r in value)
        return self._ensure_str(value)

    def _ensure_str(self, value: Any, default: str = "") -> str:
        if value is None:
            return default
        if isinstance(value, str):
            return value
        if isinstance(value, (int, float)):
            return str(value)
        if isinstance(value, dict):
            return ", ".join(f"{k}={v}" for k, v in value.items())
        if isinstance(value, list):
            return ", ".join(self._ensure_str(v) for v in value)
        return str(value)

    def _coerce_description(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            parts = ", ".join(f"{k}={v}" for k, v in value.items())
            return parts if parts else ""
        if isinstance(value, list):
            return ", ".join(self._ensure_str(v) for v in value)
        return str(value)

    def _coerce_severity(self, value: Any) -> str:
        raw = self._ensure_str(value).lower()
        if ItemSeverity.accepts(raw):
            return ItemSeverity.from_value(raw).value
        if raw in ("high", "major"):
            return ItemSeverity.MAJOR.value
        if raw in ("medium", "minor"):
            return ItemSeverity.MINOR.value
        if raw in ("low", "info"):
            return ItemSeverity.INFO.value
        if "security" in raw or "critical" in raw:
            return ItemSeverity.CRITICAL.value
        return ItemSeverity.INFO.value

    def _coerce_category(self, value: Any) -> str:
        raw = self._ensure_str(value).lower()
        try:
            return IssueCategory.from_value(raw).value
        except (ValueError, AttributeError):
            pass
        return IssueCategory.GENERAL.value

