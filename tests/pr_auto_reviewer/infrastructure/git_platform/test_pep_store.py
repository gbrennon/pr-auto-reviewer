from __future__ import annotations

from typing import Any

from pr_auto_reviewer.infrastructure.git_platform.practices.python.pep_store import PepStore

_SAMPLE_PEPS: dict[str, dict[str, Any]] = {
    "8": {
        "number": 8,
        "title": "Style Guide for Python Code",
        "status": "Active",
        "type": "Process",
        "topic": "style",
        "python_version": None,
        "url": "https://peps.python.org/pep-0008/",
    },
    "484": {
        "number": 484,
        "title": "Type Hints",
        "status": "Final",
        "type": "Standards Track",
        "topic": "typing",
        "python_version": "3.5",
        "url": "https://peps.python.org/pep-0484/",
    },
    "526": {
        "number": 526,
        "title": "Syntax for Variable Annotations",
        "status": "Final",
        "type": "Standards Track",
        "topic": "typing",
        "python_version": "3.6",
        "url": "https://peps.python.org/pep-0526/",
    },
    "557": {
        "number": 557,
        "title": "Data Classes",
        "status": "Final",
        "type": "Standards Track",
        "topic": "typing",
        "python_version": "3.7",
        "url": "https://peps.python.org/pep-0557/",
    },
    "572": {
        "number": 572,
        "title": "Assignment Expressions",
        "status": "Final",
        "type": "Standards Track",
        "topic": "syntax",
        "python_version": "3.8",
        "url": "https://peps.python.org/pep-0572/",
    },
    "585": {
        "number": 585,
        "title": "Type Hinting Generics In Standard Collections",
        "status": "Final",
        "type": "Standards Track",
        "topic": "typing",
        "python_version": "3.9",
        "url": "https://peps.python.org/pep-0585/",
    },
    "604": {
        "number": 604,
        "title": "Allow writing union types as X | Y",
        "status": "Final",
        "type": "Standards Track",
        "topic": "typing",
        "python_version": "3.10",
        "url": "https://peps.python.org/pep-0604/",
    },
    "634": {
        "number": 634,
        "title": "Structural Pattern Matching",
        "status": "Final",
        "type": "Standards Track",
        "topic": "syntax",
        "python_version": "3.10",
        "url": "https://peps.python.org/pep-0634/",
    },
    "3": {
        "number": 3,
        "title": "Withdrawn PEP",
        "status": "Withdrawn",
        "type": "Process",
        "topic": "process",
        "python_version": None,
        "url": "https://peps.python.org/pep-0003/",
    },
    "5": {
        "number": 5,
        "title": "Rejected PEP",
        "status": "Rejected",
        "type": "Standards Track",
        "topic": "syntax",
        "python_version": "3.8",
        "url": "https://peps.python.org/pep-0005/",
    },
    "10": {
        "number": 10,
        "title": "Empty topic PEP",
        "status": "Active",
        "type": "Process",
        "topic": "",
        "python_version": None,
        "url": "https://peps.python.org/pep-0010/",
    },
    "11": {
        "number": 11,
        "title": "Release PEP",
        "status": "Active",
        "type": "Process",
        "topic": "release",
        "python_version": "3.12",
        "url": "https://peps.python.org/pep-0011/",
    },
    "12": {
        "number": 12,
        "title": "Draft Standards Track",
        "status": "Draft",
        "type": "Standards Track",
        "topic": "syntax",
        "python_version": "3.12",
        "url": "https://peps.python.org/pep-0012/",
    },
    "274": {
        "number": 274,
        "title": "Dict Comprehensions",
        "status": "Final",
        "type": "Standards Track",
        "topic": "syntax",
        "python_version": "2.7, 3.0",
        "url": "https://peps.python.org/pep-0274/",
    },
}

def _make_store(peps: dict[str, Any] | None = None) -> PepStore:
    if peps is None:
        peps = dict(_SAMPLE_PEPS)

    def fake_get(url: str) -> dict[str, Any]:
        return peps

    return PepStore(http_get=fake_get)

class TestPepStoreFiltering:

    def test_excludes_withdrawn_status(self):
        store = _make_store()
        guidance = store.guidance("3.9")
        assert guidance is not None
        assert "Withdrawn" not in guidance
        assert "**PEP 3**" not in guidance

    def test_excludes_rejected_status(self):
        store = _make_store()
        guidance = store.guidance("3.10")
        assert guidance is not None
        assert "**PEP 5**" not in guidance

    def test_excludes_empty_topic(self):
        store = _make_store()
        guidance = store.guidance("3.9")
        assert guidance is not None
        assert "**PEP 10**" not in guidance

    def test_excludes_release_topic(self):
        store = _make_store()
        guidance = store.guidance("3.12")
        assert guidance is not None
        assert "**PEP 11**" not in guidance

    def test_excludes_standards_track_not_final(self):
        store = _make_store()
        guidance = store.guidance("3.12")
        assert guidance is not None
        assert "**PEP 12**" not in guidance

class TestPepStoreVersionMatching:

    def test_includes_peps_up_to_target_version(self):
        store = _make_store()
        guidance = store.guidance("3.9")
        assert guidance is not None
        assert "**PEP 484**" in guidance
        assert "**PEP 526**" in guidance
        assert "**PEP 557**" in guidance
        assert "**PEP 585**" in guidance

    def test_excludes_peps_beyond_target_version(self):
        store = _make_store()
        guidance = store.guidance("3.9")
        assert guidance is not None
        assert "**PEP 604**" not in guidance
        assert "**PEP 634**" not in guidance

    def test_includes_version_agnostic_peps(self):
        store = _make_store()
        guidance = store.guidance("3.9")
        assert guidance is not None
        assert "**PEP 8**" in guidance

    def test_multi_version_pep_applies_when_any_match(self):
        store = _make_store()
        guidance = store.guidance("3.9")
        assert guidance is not None
        assert "**PEP 274**" in guidance

class TestPepStoreRanking:

    def test_standards_track_ranked_higher_than_process(self):
        store = _make_store()
        guidance = store.guidance("3.9")
        assert guidance is not None
        lines = guidance.split("\n")
        pep8_idx = next(i for i, l in enumerate(lines) if "**PEP 8**" in l)
        pep484_idx = next(i for i, l in enumerate(lines) if "**PEP 484**" in l)
        assert pep484_idx < pep8_idx

    def test_version_proximity_adds_score(self):
        store = _make_store()
        guidance = store.guidance("3.9")
        assert guidance is not None
        lines = guidance.split("\n")
        pep585_idx = next(i for i, l in enumerate(lines) if "**PEP 585**" in l)
        pep484_idx = next(i for i, l in enumerate(lines) if "**PEP 484**" in l)
        assert pep585_idx < pep484_idx

class TestPepStoreGuidanceFormat:

    def test_returns_none_when_no_relevant_peps(self):
        store = _make_store({})
        assert store.guidance("3.9") is None

    def test_includes_python_version_in_header(self):
        store = _make_store()
        guidance = store.guidance("3.10")
        assert guidance is not None
        assert "Python 3.10" in guidance

    def test_includes_type_and_status(self):
        store = _make_store()
        guidance = store.guidance("3.9")
        assert guidance is not None
        assert "Standards Track/Final" in guidance
        assert "Process/Active" in guidance

    def test_includes_pep_urls(self):
        store = _make_store()
        guidance = store.guidance("3.9")
        assert guidance is not None
        assert "pep-0484/" in guidance

class TestPepStoreCaching:

    def test_fetches_only_once(self):
        call_count = 0

        def counting_get(url: str) -> dict[str, Any]:
            nonlocal call_count
            call_count += 1
            return dict(_SAMPLE_PEPS)

        store = PepStore(http_get=counting_get)
        store.guidance("3.9")
        store.guidance("3.10")
        assert call_count == 1

class TestPepStoreErrorHandling:

    def test_guidance_handles_fetch_failure(self):
        def failing_get(url: str) -> dict[str, Any]:
            raise RuntimeError("Network error")

        store = PepStore(http_get=failing_get)
        assert store.guidance("3.9") is None

    def test_guidance_handles_invalid_version(self):
        store = _make_store()
        assert store.guidance("not.a.version") is None

class TestPepStoreMalformedVersions:

    def test_skips_malformed_python_version_in_version_applies(self):
        """PEPs with malformed python_version (e.g. "3.x") should be skipped."""
        peps = {
            "100": {
                "number": 100,
                "title": "Bad version PEP",
                "status": "Final",
                "type": "Standards Track",
                "topic": "syntax",
                "python_version": "3.x",
                "url": "https://peps.python.org/pep-0100/",
            },
            "8": {
                "number": 8,
                "title": "Style Guide",
                "status": "Active",
                "type": "Process",
                "topic": "style",
                "python_version": None,
                "url": "https://peps.python.org/pep-0008/",
            },
        }
        store = PepStore(http_get=lambda url: peps)
        guidance = store.guidance("3.9")
        assert guidance is not None
        assert "**PEP 100**" not in guidance
        assert "**PEP 8**" in guidance

    def test_malformed_version_in_rank_does_not_crash(self):
        peps = {
            "200": {
                "number": 200,
                "title": "Mixed version PEP",
                "status": "Final",
                "type": "Standards Track",
                "topic": "typing",
                "python_version": "3.x, 3.7",
                "url": "https://peps.python.org/pep-0200/",
            },
        }
        store = PepStore(http_get=lambda url: peps)
        guidance = store.guidance("3.9")
        assert guidance is not None
        assert "**PEP 200**" in guidance

class TestPepStoreParseVersion:

    def test_guidance_handles_major_only_version(self):
        """Version string with only major (e.g. "3") is invalid."""
        store = _make_store()
        assert store.guidance("3") is None
