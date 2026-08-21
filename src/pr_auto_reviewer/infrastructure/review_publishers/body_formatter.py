from __future__ import annotations

import logging
from pathlib import Path

import jinja2

from pr_auto_reviewer.domain.value_objects.code_review import CodeReview

logger = logging.getLogger(__name__)


class ReviewBodyRenderer:
    """Renders review bodies using Jinja2 templates.

    Dependency-injected template directory allows flexible template
    locations without hardcoding paths in the class.
    """

    def __init__(self, template_dir: Path) -> None:
        self._template_dir = template_dir
        _jinja_env = jinja2.Environment(
            loader=jinja2.FileSystemLoader(str(template_dir)),
            keep_trailing_newline=True,
        )
        self._template = _jinja_env.get_template("review_output.j2")

    def render(self, review: CodeReview) -> str:
        verdict_text = review.verdict.value.replace("_", " ").title()

        numbered_items = []
        for item in review.items:
            numbered_items.append(
                {
                    "id": item.id,
                    "severity": item.severity,
                    "category": item.category,
                    "file_path": item.file_path,
                    "line": item.line,
                    "description": item.description,
                    "current_code": item.current_code,
                    "suggested_fix": item.suggested_fix,
                }
            )

        numbered_praise = []
        for p in review.praise:
            numbered_praise.append({
                "description": p.description,
                "file_path": p.file_path,
            })

        suggestions_raw = getattr(review, "suggestions", [])
        numbered_suggestions = []
        for s in suggestions_raw:
            numbered_suggestions.append({
                "id": s.id,
                "description": s.description,
                "file_path": s.file_path,
                "line": s.line,
                "current_code": s.current_code,
                "suggested_fix": s.suggested_fix,
            })

        return self._template.render(
            review=review,
            verdict_text=verdict_text,
            items=numbered_items,
            praise=numbered_praise,
            suggestions=numbered_suggestions,
        )