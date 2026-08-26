"""Tests for IdentifierGroundingFilterService."""

from __future__ import annotations

from pr_auto_reviewer.application.services.identifier_grounding_filter_service import (
    IdentifierGroundingFilterService,
)


class TestIdentifierGroundingFilter:
    """Generated prompts may only cite identifiers seen in evidence."""

    def test_nonexistent_class_name_is_genericized(self) -> None:
        service = IdentifierGroundingFilterService()

        result = service.strip_unobserved(
            "Refactor AppInbound so it validates ShallowInbound ordering.",
            evidence="The phase examined PortLevel ordering rules.",
        )

        assert "AppInbound" not in result
        assert "ShallowInbound" not in result
        assert "[unverified reference]" in result

    def test_real_identifier_from_evidence_passes_through(self) -> None:
        service = IdentifierGroundingFilterService()
        text = "Keep the PortLevel ordering contract intact."

        result = service.strip_unobserved(
            text, evidence="...findings about PortLevel depth...",
        )

        assert "PortLevel" in result
        assert "[unverified reference]" not in result

    def test_repo_path_citation_is_checked(self) -> None:
        service = IdentifierGroundingFilterService()

        result = service.strip_unobserved(
            "Move this into src/ports/app_inbound.py for clarity.",
            evidence="discussed src/ports/app_inbound.py earlier",
        )

        assert "src/ports/app_inbound.py" in result

        hallucinated = service.strip_unobserved(
            "Move this into src/ports/fake_module.py for clarity.",
            evidence="nothing about that file",
        )

        assert "fake_module" not in hallucinated

    def test_plain_prose_is_untouched(self) -> None:
        service = IdentifierGroundingFilterService()
        text = "Stay on task and re-read the diff before concluding."

        assert service.strip_unobserved(text, "") == text

    def test_empty_text_returns_empty(self) -> None:
        service = IdentifierGroundingFilterService()

        assert service.strip_unobserved("", "evidence") == ""
