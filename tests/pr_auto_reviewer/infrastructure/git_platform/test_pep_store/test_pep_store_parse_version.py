from ._helpers import *


class TestPepStoreParseVersion:

    def test_guidance_handles_major_only_version(self):
        """Version string with only major (e.g. "3") is invalid."""
        store = _make_store()
        assert store.guidance("3") is None

