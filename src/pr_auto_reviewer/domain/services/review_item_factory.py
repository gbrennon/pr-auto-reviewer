"""ReviewItemFactory — construct validated ReviewItem domain objects from parsed dicts."""

import logging
import re
import uuid as _uuid
from dataclasses import replace
from pathlib import Path
from typing import Any, ClassVar

from pr_auto_reviewer.domain.entities.review_item import ReviewItem
from pr_auto_reviewer.domain.value_objects.code_review import CodeReview
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

    _SNIPPET_SEARCH_WINDOW = 5

    @classmethod
    def _locate_snippet(
        cls,
        file_lines: list[str],
        current_code: str,
        claimed_line: int,
    ) -> int | None:
        """Return the 1-based line where *current_code* anchors in the file.

        Matches multi-line snippets by their normalized non-blank lines
        and single-line snippets by stripped equality. The search starts
        in a window around *claimed_line* — models are frequently off by
        a few lines on poorly written code — then widens to the whole
        file. None means nothing matched anywhere; callers keep the
        finding with its claimed anchor instead of discarding a real
        issue over an imprecise snippet.
        """
        snippet = [
            line.strip() for line in current_code.splitlines() if line.strip()
        ]
        if not snippet:
            return None
        total = len(file_lines)
        span = len(snippet)
        window = range(
            max(0, claimed_line - 1 - cls._SNIPPET_SEARCH_WINDOW),
            min(total - span + 1, claimed_line - 1 + cls._SNIPPET_SEARCH_WINDOW + 1),
        )
        order = list(window) + [
            i for i in range(max(0, total - span + 1)) if i not in set(window)
        ]
        for start in order:
            if all(
                file_lines[start + offset].strip() == snippet[offset]
                for offset in range(span)
            ):
                return start + 1
        return None

    @classmethod
    def generate_id(cls, existing_ids: frozenset[str] = frozenset()) -> str:
        """Generate a unique ID for a review item.

        Uses the 4 *lowest* hex digits of a uuid7 plus a 2-digit
        process counter.  The low bits are freshly random on every
        call; the high bits encode the unix-millisecond timestamp and
        stay constant within minute-scale windows, which made IDs
        repeat across runs (every review produced ``1a03xx``).
        """
        if not hasattr(cls, "_id_counter"):
            cls._id_counter = 0

        def _candidate() -> str:
            cls._id_counter += 1
            random_part = format(_uuid.uuid7().int & 0xFFFF, "04x")
            counter_part = format(cls._id_counter, "02x")
            return f"{random_part}{counter_part}"

        candidate = _candidate()
        while candidate in existing_ids:
            candidate = _candidate()
        return candidate

    @classmethod
    def ensure_unique_ids(cls, review: CodeReview) -> CodeReview:
        """Return a CodeReview whose items, suggestions, and praise all carry globally unique ids."""

        used: set[str] = set()
        items = [cls._ensure_unique_id(item, used) for item in review.items]
        suggestions = [cls._ensure_unique_id(s, used) for s in review.suggestions]
        praise = [cls._ensure_unique_id(p, used) for p in review.praise]
        return replace(review, items=items, suggestions=suggestions, praise=praise)

    @classmethod
    def _ensure_unique_id(cls, item: ReviewItem, used: set[str]) -> ReviewItem:
        """Return *item* with a non-empty id unique against *used*, registering it."""

        if item.id and item.id not in used:
            used.add(item.id)
            return item
        candidate = cls.generate_id(frozenset(used))
        used.add(candidate)
        return replace(item, id=candidate)

    @classmethod
    def _locate_symbol_range(cls,
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
    def _read_evidence(cls,
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

    @classmethod
    def _resolve_file_path(cls,
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

    @classmethod
    def create(
        cls,
        item_dicts: list[dict[str, Any]],
        repo_path: Path | None,
        changed_files: list[str] | None = None,
        existing_ids: frozenset[str] = frozenset(),
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
        if repo_path is None or repo_path == "":
            logger.debug("repo_path is None or empty string")
            repo_root = None
        elif isinstance(repo_path, Path):
            logger.debug("repo_path is Path instance")
            repo_root = repo_path
        else:
            logger.debug(f"repo_path is other type: {type(repo_path)}, value: {repo_path!r}")
            repo_root = Path(repo_path)
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
            anchor_unverified = False

            if repo_root is not None and not file_path:
                grounded = cls._ground_description(
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
                full_path, file_path = cls._resolve_file_path(
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
                    except ValueError:
                        line_num = 0

                    located = (
                        cls._locate_snippet(
                            file_lines, current_code, line_num or 1
                        )
                        if current_code
                        else None
                    )
                    if located is not None:
                        line_num = located
                        line_str = str(located)
                    elif not (1 <= line_num <= len(file_lines)):
                        reason = (
                            f"line {line_str} out of range in "
                            f"{file_path} ({len(file_lines)} lines)"
                        )
                        logger.warning("Skipping finding — %s", reason)
                        skip_reasons.append(reason)
                        continue
                    elif current_code:
                        anchor_unverified = True
                        logger.warning(
                            "Downgrading finding with unverified code"
                            " anchor to info at %s:%s",
                            file_path,
                            line_str,
                        )
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
                    for pattern in cls._FABRICATED_ERROR_PATTERNS
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
                current_code = cls._read_evidence(
                    full_path, repo_root, line_str, description
                )

            if not line_str and full_path is not None:
                hit = cls._locate_symbol_range(full_path, description)
                if hit is not None:
                    line_str = hit

            if current_code and not suggested_fix:
                suggested_fix = current_code

            severity = ItemSeverity.from_value(
                str(item_dict.get("severity", "info"))
            )
            description = str(item_dict.get("description", ""))
            cls._warn_on_intensity_mismatch(severity, description)
            if anchor_unverified:
                severity = ItemSeverity.INFO
                description = f"{description} [anchor_unverified]"

            review_item = ReviewItem(
                severity=severity,
                category=IssueCategory.from_value(
                    str(item_dict.get("category", "maintainability"))
                ),
                file_path=file_path,
                description=description,
                line=line_str,
                id=cls.generate_id(existing_ids),
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
    def _warn_on_intensity_mismatch(
        severity: ItemSeverity, description: str,
    ) -> None:
        """Warn when the description's intensity contradicts *severity*.

        Observed live (1a030c): a description calling something a
        "critical flaw" published under ``minor/maintainability``.
        The mismatch is a fabrication signal, so it is logged loudly.
        """
        description_lower = description.lower()
        intense = any(
            word in description_lower
            for word in ("critical", "severe", "crash", "dangerous")
        )
        if intense and severity in (ItemSeverity.INFO, ItemSeverity.MINOR):
            logger.warning(
                "Severity/intensity mismatch: description claims "
                "critical impact but severity is %s — %s",
                severity.value,
                description[:80],
            )
