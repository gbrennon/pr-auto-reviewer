"""ReviewItemFactory — construct validated ReviewItem domain objects from parsed dicts."""

import hashlib
import logging
from pathlib import Path
from typing import Any, ClassVar

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity

logger = logging.getLogger(__name__)


class ReviewItemFactory:
    """Construct validated ReviewItem domain objects from parsed item dicts.

    Validates that each ``file_path`` exists in the repository;
    hallucinated paths are skipped with a warning. Returns validated
    items and a list of human-readable skip reasons for feedback.
    """

    _FABRICATED_ERROR_PATTERNS: ClassVar[tuple[str, ...]] = (
        "file not found",
        "unable to verify",
        "cannot access",
        "could not read",
        "does not exist",
        "not accessible",
        "not found in",
        "could not be found",
        "unable to locate",
    )

    def create(
        self,
        item_dicts: list[dict[str, Any]],
        repo_path: str,
        changed_files: list[str] | None = None,
    ) -> tuple[list[ReviewItem], list[str]]:
        """Construct ReviewItem domain objects from parsed item dicts.

        Validates that each ``file_path`` exists in the repository;
        hallucinated paths are skipped with a warning.
        """
        repo_root = Path(repo_path) if repo_path else None
        review_items: list[ReviewItem] = []
        skip_reasons: list[str] = []
        default_file = (
            changed_files[0] if changed_files and len(changed_files) == 1 else ""
        )
        for item_dict in item_dicts:
            if not isinstance(item_dict, dict):
                logger.warning("Skipping non-dict item: %s", str(item_dict)[:200])
                continue
            file_path = str(item_dict.get("file", ""))
            if file_path.startswith(("a/", "b/")):
                file_path = file_path[2:]
            if not file_path and default_file:
                file_path = default_file
            full_path: Path | None = None
            if repo_root is not None and file_path:
                full_path = repo_root / file_path
                if not full_path.exists():
                    reason = f"file not found: {file_path}"
                    logger.warning("Skipping finding — %s", reason)
                    skip_reasons.append(reason)
                    continue
                try:
                    file_path = str(
                        full_path.resolve().relative_to(repo_root.resolve())
                    )
                except ValueError:
                    pass
            current_code = str(item_dict.get("current_code", ""))
            suggested_fix = str(item_dict.get("suggested_fix", ""))
            line_str = str(item_dict.get("line", ""))

            if full_path is not None and file_path and (
                line_str or current_code
            ):
                file_lines = full_path.read_text().splitlines()

                if line_str:
                    try:
                        line_num = int(line_str)

                        if not (1 <= line_num <= len(file_lines)):
                            reason = (
                                f"line {line_str} out of range in "
                                f"{file_path} ({len(file_lines)} lines)"
                            )
                            logger.warning(
                                "Skipping finding — %s", reason
                            )
                            skip_reasons.append(reason)
                            continue

                        if current_code:
                            actual_line = file_lines[
                                line_num - 1
                            ].strip()

                            if current_code.strip() != actual_line:
                                reason = (
                                    f"code mismatch at "
                                    f"{file_path}:{line_str}"
                                )
                                logger.warning(
                                    "Skipping finding — %s", reason
                                )
                                skip_reasons.append(reason)
                                continue
                    except ValueError:
                        pass
            description = str(item_dict.get("description", ""))

            if (
                repo_root is not None
                and file_path
                and not description
            ):
                reason = f"no code evidence in {file_path}"
                logger.warning("Skipping finding — %s", reason)
                skip_reasons.append(reason)
                continue

            if (
                repo_root is not None
                and file_path
                and not current_code
                and description
            ):
                description_lower = description.lower()

                if any(
                    pattern in description_lower
                    for pattern in self._FABRICATED_ERROR_PATTERNS
                ):
                    reason = (
                        f"fabricated narrative in {file_path}: "
                        f"{description[:80]}"
                    )
                    logger.warning(
                        "Skipping finding — %s", reason
                    )
                    skip_reasons.append(reason)
                    continue

            item_id = self._generate_id(
                file_path, description, len(review_items)
            )
            review_item = ReviewItem(
                number=len(review_items) + 1,
                severity=ItemSeverity.from_value(
                    str(item_dict.get("severity", "info"))
                ),
                category=IssueCategory.from_value(
                    str(item_dict.get("category", "maintainability"))
                ),
                file_path=file_path,
                description=str(item_dict.get("description", "")),
                line=str(item_dict.get("line", "")),
                id=item_id,
                current_code=current_code,
                suggested_fix=suggested_fix,
            )
            review_items.append(review_item)

        if skip_reasons:
            logger.info(
                "%d items parsed, %d skipped: %s",
                len(item_dicts),
                len(skip_reasons),
                ", ".join(skip_reasons),
            )
        return review_items, skip_reasons

    @staticmethod
    def _generate_id(file_path: str, description: str, index: int) -> str:
        """Generate a short 4-character hex ID for a review item."""
        seed = f"{file_path}:{description}:{index}"
        digest = hashlib.sha256(seed.encode()).hexdigest()
        return digest[:4]
