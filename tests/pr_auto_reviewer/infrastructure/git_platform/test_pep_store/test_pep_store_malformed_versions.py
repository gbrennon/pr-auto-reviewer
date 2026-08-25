from ._helpers import *


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

