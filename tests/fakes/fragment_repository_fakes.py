"""Stub ``PromptFragmentRepository`` implementations for test use."""

from pr_auto_reviewer.domain.fragments.entities.prompt_fragment import PromptFragment


class StubFragmentRepository:
    """Stub repository returning pre-configured fragments and recording calls."""

    def __init__(
        self,
        *,
        by_language: list[PromptFragment] | None = None,
        universal: list[PromptFragment] | None = None,
    ) -> None:
        self._by_language = by_language or []
        self._universal = universal or []
        self.find_by_language_calls: list[str] = []
        self.find_universal_calls: int = 0

    def find_by_language(self, language: str) -> list[PromptFragment]:
        self.find_by_language_calls.append(language)
        return [f for f in self._by_language if f.language == language]

    def find_universal(self) -> list[PromptFragment]:
        self.find_universal_calls += 1
        return list(self._universal)

    def find_by_id(self, fragment_id: str) -> PromptFragment | None:
        for f in self._by_language + self._universal:
            if f.id == fragment_id:
                return f
        return None
