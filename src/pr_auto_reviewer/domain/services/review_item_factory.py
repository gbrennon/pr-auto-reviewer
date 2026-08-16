"""ReviewItemFactory — construct validated ReviewItem domain objects from parsed dicts."""

import hashlib
import logging
import re
from pathlib import Path
from typing import Any, ClassVar

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.issue_category import IssueCategory
from pr_auto_reviewer.domain.value_objects.item_severity import ItemSeverity

logger = logging.getLogger(__name__)


class ReviewItemFactory:
    """Construct validated ReviewItem domain objects from parsed item dicts.

    Enforces the domain invariant that every finding must carry a
    meaningful description. ``file_path``, ``current_code``, and
    ``suggested_fix`` are preserved when present, but findings are not
    discarded solely for missing code snippets — otherwise almost every
    real review is emptied out. Files that cannot be resolved and lines
    that fall out of range are still skipped with a descriptive reason so
    the caller can request a re-review.

    Additionally validates that each ``file_path`` exists in the repository
    and that ``current_code`` matches the actual file content at the
    claimed line; hallucinated paths are skipped with a warning. Returns
    validated items and a list of human-readable skip reasons for feedback.
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
        repo_path: Path | None,
        changed_files: list[str] | None = None,
    ) -> tuple[list[ReviewItem], list[str]]:
        """Construct ReviewItem domain objects from parsed item dicts.

        Enforces the domain invariant that every finding must carry a
        meaningful description. ``file_path``, ``current_code``, and
        ``suggested_fix`` are preserved when present, but findings are
        not discarded solely for missing code snippets. This prevents a
        narrative review from being silently emptied out.

        Additionally validates that each ``file_path`` exists in the
        repository and that ``current_code`` matches the actual file
        content at the claimed line; hallucinated paths are skipped.
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
            current_code = str(item_dict.get("current_code", ""))
            suggested_fix = str(item_dict.get("suggested_fix", ""))
            line_str = str(item_dict.get("line", ""))

            if repo_root is not None and not file_path:
                grounded = self._ground_description(
                    str(item_dict.get("description", "")),
                    repo_root,
                    changed_files,
                )
                if grounded is not None:
                    file_path = grounded[0]
                    if not line_str:
                        line_str = grounded[1]
                    if not current_code:
                        current_code = grounded[2]

            full_path: Path | None = None
            if repo_root is not None and file_path:
                full_path, file_path = self._resolve_file_path(
                    file_path, repo_root, changed_files
                )
                if full_path is None:
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

            if not current_code and full_path is not None:
                current_code = self._read_evidence(
                    full_path, repo_root, line_str, description
                )

            if not line_str and full_path is not None:
                hit = self._locate_symbol_range(full_path, description)
                if hit is not None:
                    line_str = hit

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
                line=line_str,
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

    @classmethod
    def _extract_symbols(cls, description: str) -> list[str]:
        """Extract candidate symbol names referenced in a finding description."""
        backticked = re.findall(r"`([a-zA-Z_][a-zA-Z0-9_.]*)`", description)
        symbols = [s for s in backticked if len(s) > 1]
        for match in re.finditer(
            r"\b(def |class )?([a-z_][a-z0-9_]{2,})\b", description, re.IGNORECASE
        ):
            candidate = match.group(2)
            if candidate not in symbols:
                symbols.append(candidate)
        return symbols

    @classmethod
    def _ground_description(
        cls,
        description: str,
        repo_root: Path,
        changed_files: list[str] | None,
    ) -> tuple[str, str, str] | None:
        """Locate the symbol named in *description* inside the repository.

        Returns ``(file_path, line, current_code)`` when a match is found
        in one of the changed files, else None.
        """
        if not description:
            return None
        symbols = cls._extract_symbols(description)
        if not symbols:
            return None
        search_files = [f for f in (changed_files or []) if f and not f.startswith("a/")]
        for symbol in symbols:
            for cf in search_files or []:
                try:
                    content = (repo_root / cf).read_text()
                except (OSError, UnicodeDecodeError):
                    continue
                hit = cls._symbol_hit(content, symbol)
                if hit is not None:
                    line_num, excerpt = hit
                    return cf, str(line_num), excerpt
        return None

    @staticmethod
    def _locate_symbol_range(
        full_path: Path, description: str,
    ) -> str | None:
        """Return a line range ``"start-end"`` enclosing the symbol block."""
        symbols = ReviewItemFactory._extract_symbols(description)
        if not symbols:
            return None
        try:
            lines = full_path.read_text().splitlines()
        except (OSError, UnicodeDecodeError):
            return None
        for symbol in symbols:
            pattern = re.compile(rf"\b{re.escape(symbol)}\b")
            for idx, line in enumerate(lines):
                if pattern.search(line):
                    end = idx
                    end += 1
                    while end < len(lines) and lines[end].strip():
                        end += 1
                    while end < len(lines) and not lines[end].strip():
                        end += 1
                    while end < len(lines) and lines[end].startswith((" ", "\t")):
                        end += 1
                    return f"{idx + 1}-{max(end, idx + 1)}"
        return None

    @classmethod
    def _symbol_hit(cls, content: str, symbol: str) -> tuple[int, str] | None:
        """Return ``(1-based line, surrounding lines excerpt)`` for a hit."""
        pattern = re.compile(rf"\b{re.escape(symbol)}\b")
        lines = content.splitlines()
        for idx, line in enumerate(lines):
            if pattern.search(line):
                start = max(0, idx - 1)
                window = "\n".join(lines[start : idx + 4])
                return idx + 1, window.strip()
        return None

    @staticmethod
    def _read_evidence(
        full_path: Path,
        repo_root: Path,
        line_str: str,
        description: str,
    ) -> str:
        """Read a focused slice of the file around the claimed location."""
        try:
            file_lines = full_path.read_text().splitlines()
        except (OSError, UnicodeDecodeError):
            return ""
        if not file_lines:
            return ""
        if line_str:
            try:
                line_num = int(line_str)
                if 1 <= line_num <= len(file_lines):
                    start = max(0, line_num - 2)
                    return "\n".join(
                        file_lines[start : line_num + 3]
                    ).strip()
            except ValueError:
                pass
        for symbol in ReviewItemFactory._extract_symbols(description):
            for idx, line in enumerate(file_lines):
                if re.search(rf"\b{re.escape(symbol)}\b", line):
                    start = max(0, idx - 1)
                    return "\n".join(
                        file_lines[start : idx + 4]
                    ).strip()
        return "\n".join(file_lines[:500]).strip()

    @staticmethod
    def _resolve_file_path(
        file_path: str,
        repo_root: Path,
        changed_files: list[str] | None,
    ) -> tuple[Path | None, str]:
        """Resolve a potentially partial file path against changed_files.

        When the LLM returns a short or partial path (e.g. ``module.py``
        or ``pkg/module.py``), this method attempts to find the full
        repo-relative path by matching against the known changed files.
        Returns ``(full_path, resolved_file_path)`` on success, or
        ``(None, original_file_path)`` when no match is found.
        """
        direct_path = repo_root / file_path
        if direct_path.exists():
            return direct_path, file_path

        if not changed_files:
            return None, file_path

        cleaned = file_path.lstrip("/")
        candidates: list[tuple[int, str]] = []

        for cf in changed_files:
            cf_clean = cf[2:] if cf.startswith(("a/", "b/")) else cf

            if cf_clean == cleaned:
                candidates.append((0, cf_clean))
                continue

            if cf_clean.endswith("/" + cleaned):
                candidates.append((1, cf_clean))
                continue

            if "/" not in cleaned:
                cf_basename = (
                    cf_clean.rsplit("/", 1)[-1]
                    if "/" in cf_clean
                    else cf_clean
                )
                if cf_basename == cleaned:
                    candidates.append((2, cf_clean))
                    continue

        if not candidates:
            return None, file_path

        candidates.sort(key=lambda x: (x[0], len(x[1])))
        matched = candidates[0][1]
        return repo_root / matched, matched
