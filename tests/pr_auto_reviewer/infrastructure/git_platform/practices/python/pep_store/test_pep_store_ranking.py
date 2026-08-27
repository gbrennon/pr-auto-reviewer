from ._helpers import *


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

