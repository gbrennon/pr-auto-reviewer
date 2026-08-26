from ._helpers import *


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

