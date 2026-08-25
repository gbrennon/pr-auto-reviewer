from ._helpers import *


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

