"""Tests for ArchitectureDetector."""

import pytest

from pr_auto_reviewer.infrastructure.context.architecture_detector import (
    ArchitectureDetector,
)


class TestReturnsUnknown:
    """Tests for unknown architecture detection."""

    @pytest.fixture
    def detector(self) -> ArchitectureDetector:
        return ArchitectureDetector()

    def test_returns_unknown_for_empty(self, detector: ArchitectureDetector) -> None:
        """Returns unknown for empty path list."""
        assert detector.detect([]) == "unknown"

    def test_returns_unknown_for_unrecognized(self, detector: ArchitectureDetector) -> None:
        """Returns unknown for unrecognized patterns."""
        paths = ["src/main.rs", "README.md", "src/utils/helper.go"]
        assert detector.detect(paths) == "unknown"

    def test_returns_unknown_for_partial_match(self, detector: ArchitectureDetector) -> None:
        """Returns unknown when only some markers present."""
        paths = ["src/domain/model.rs", "src/services/service.rs"]
        assert detector.detect(paths) == "unknown"

    def test_returns_unknown_for_no_src_folders(self, detector: ArchitectureDetector) -> None:
        """Returns unknown for typical Go project structure."""
        paths = ["main.go", "cmd/server/main.go", "internal/handler.go"]
        assert detector.detect(paths) == "unknown"
