"""Auto-discover diff+review fixture pairs for parametrized tests.

Add fixtures with:  make capture-fixture REPO=... PR=... NAME=<name> REVIEW=1
Tests automatically pick them up — no code changes needed.

Each fixture is stored as a triplet in tests/fixtures/diffs/:
    <name>.diff      — unified diff
    <name>.json      — metadata: owner, repo, full_repo, pr_number, head_sha, title

Review output (optional) in tests/fixtures/reviews/:
    <name>.json      — verdict, summary, items, + same metadata fields
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).resolve().parent
DIFFS_DIR = FIXTURES_DIR / "diffs"
REVIEWS_DIR = FIXTURES_DIR / "reviews"


def _load_json(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def _discover_pairs() -> list[dict]:
    """Scan diffs/ for <name>.diff + <name>.json metadata pairs.

    Returns list of dicts with keys:
        name, diff_path, meta, review_path (or None)
    """
    pairs: list[dict] = []
    if not DIFFS_DIR.exists():
        return pairs

    for diff_file in sorted(DIFFS_DIR.glob("*.diff")):
        name = diff_file.stem
        meta_file = DIFFS_DIR / f"{name}.json"
        review_file = REVIEWS_DIR / f"{name}.json"

        if not meta_file.exists():
            continue  # skip legacy diffs without metadata

        pairs.append({
            "name": name,
            "diff_path": diff_file,
            "meta": _load_json(meta_file),
            "review_path": review_file if review_file.exists() else None,
        })

    return pairs


@pytest.fixture
def fixture_pair(request):
    """Parametrized fixture returning a dict with:
        name, diff_path, meta, review_path

    Usage:
        @pytest.mark.parametrize("fixture_pair", discovered_pairs(), indirect=True)
    """
    return request.param


def discovered_pairs() -> list[dict]:
    """Return all discovered pairs for @pytest.mark.parametrize."""
    return _discover_pairs()


@pytest.fixture
def fixture_loaded(request):
    """Parametrized fixture returning (name, diff_text, meta, review_dict_or_None).

    Usage:
        @pytest.mark.parametrize("fixture_loaded",
            [(p["name"], p["diff_path"], p["meta"], p["review_path"])
             for p in discovered_pairs()], indirect=True)
    """
    name, diff_path, meta, review_path = request.param
    diff_text = diff_path.read_text()
    review = _load_json(review_path) if review_path else None
    return name, diff_text, meta, review


def discovered_pairs_loaded() -> list[tuple]:
    """Pairs as tuples for parametrize — pre-loads metadata only."""
    return [
        (p["name"], p["diff_path"], p["meta"], p["review_path"])
        for p in _discover_pairs()
    ]
