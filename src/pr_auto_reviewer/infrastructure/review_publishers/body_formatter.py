from __future__ import annotations

import logging
from pathlib import Path

import jinja2

from pr_auto_reviewer.domain.value_objects.code_review import CodeReview

logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent.parent / "llm" / "templates"
_jinja_env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(str(_TEMPLATES_DIR)),
    keep_trailing_newline=True,
)

class ReviewBodyFormatter:
    def format(self, review: CodeReview, start_number: int = 0) -> str:
        verdict_text = review.verdict.value.replace("_", " ").title()

        idx = start_number
        numbered_items = []
        for item in review.items:
            numbered_items.append(
                {
                    "number": idx,
                    "severity": item.severity,
                    "category": item.category,
                    "file_path": item.file_path,
                    "line": item.line,
                    "description": item.description,
                    "current_code": item.current_code,
                    "suggested_fix": item.suggested_fix,
                }
            )
            idx += 1

        numbered_praise = []
        for p in review.praise:
            numbered_praise.append({
                "description": p.description,
                "file": p.file,
            })

        suggestions_raw = getattr(review, "suggestions", [])
        numbered_suggestions = []
        for s in suggestions_raw:
            numbered_suggestions.append({
                "number": idx,
                "description": s.description,
                "file": s.file,
                "line": s.line,
                "current_code": s.current_code,
                "suggested_code": s.suggested_code,
            })
            idx += 1

        template = _jinja_env.get_template("review_output.j2")
        return template.render(
            review=review,
            verdict_text=verdict_text,
            items=numbered_items,
            praise=numbered_praise,
            suggestions=numbered_suggestions,
        )
