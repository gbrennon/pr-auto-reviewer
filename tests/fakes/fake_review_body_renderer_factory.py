"""Shared ReviewBodyRenderer construction for test rendering."""

from pathlib import Path

from pr_auto_reviewer.infrastructure.review_publishers.body_formatter import (
    ReviewBodyRenderer,
)


class FakeReviewBodyRendererFactory:
    """Build the project's `ReviewBodyRenderer` bound to its template directory."""

    TEMPLATE_DIR = Path("src/pr_auto_reviewer/infrastructure/templates")

    @classmethod
    def make(cls) -> ReviewBodyRenderer:
        """Return a renderer configured with the project's template directory."""
        return ReviewBodyRenderer(template_dir=cls.TEMPLATE_DIR)