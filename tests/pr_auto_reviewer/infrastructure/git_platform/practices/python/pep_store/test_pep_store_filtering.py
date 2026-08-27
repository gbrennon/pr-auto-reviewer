from ._helpers import *


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

