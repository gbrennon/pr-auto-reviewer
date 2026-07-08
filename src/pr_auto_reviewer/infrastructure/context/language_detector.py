"""LanguageDetector — detects primary language from file extensions."""

from __future__ import annotations

from collections import Counter

_EXTENSION_LANGUAGE_MAP: dict[str, str] = {
    ".py": "python",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".kt": "kotlin",
    ".ts": "typescript",
    ".js": "javascript",
    ".rb": "ruby",
    ".cs": "csharp",
    ".swift": "swift",
}

class LanguageDetector:
    """Detects the primary programming language from a list of file paths.

    Uses file-extension heuristics with a majority-vote strategy.
    """

    def detect(self, file_paths: list[str]) -> str:
        """Return the most common language, or ``"unknown"``.

        Args:
            file_paths: Absolute or relative paths from the diff.

        Returns:
            Language key (e.g. ``"python"``) or ``"unknown"``.
        """
        counts: Counter[str] = Counter()
        for path in file_paths:
            for ext, lang in _EXTENSION_LANGUAGE_MAP.items():
                if path.endswith(ext):
                    counts[lang] += 1
                    break
        if counts:
            return counts.most_common(1)[0][0]
        return "unknown"
